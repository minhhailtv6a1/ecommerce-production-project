"""Embed labeled training images with CLIP and ingest them into Pinecone."""

import argparse
import json
import logging
import re
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from app.core.config import settings
from app.repositories.pinecone import (
    PineconeDocumentRepository,
    PineconeSdkUnavailableError,
    create_pinecone_client,
)
from app.services.image_ingestion import (
    ImageDatasetError,
    ImageEmbeddingDependencyError,
    ImageEmbeddingError,
    IngestionCheckpoint,
    OpenClipImageEmbedder,
    discover_image_dataset,
    ingest_images,
)
from app.services.catalog_links import CatalogLinkError, load_catalog_vector_links
from app.services.pinecone_index import (
    PineconeIndexConfigurationError,
    PineconeIndexMismatchError,
    PineconeIndexNotFoundError,
    index_definition_from_settings,
    validate_pinecone_index,
)


logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate OpenAI CLIP ViT-B-32 image embeddings and upsert labeled "
            "documents into the configured Pinecone namespace."
        )
    )
    parser.add_argument(
        "--catalog-manifest",
        type=Path,
        default=Path("data/product_images.csv"),
        help=(
            "Product-image CSV used to attach product_id and image_id when a "
            "selected vector is part of the catalog."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Run model inference and Pinecone writes. The default is a dry run.",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="Override INGEST_DATASET_PATH for this run.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Override INGEST_BATCH_SIZE for model inference and upserts.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most this many pending images, useful for a live smoke test.",
    )
    parser.add_argument(
        "--each",
        action="store_true",
        help=(
            "Apply --limit independently to every label directory. For example, "
            "--limit 10 --each processes up to 10 pending images from each label."
        ),
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda"),
        default=None,
        help="Override CLIP_DEVICE for this run.",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Override the append-only resume checkpoint path.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore and do not update the local ingestion checkpoint.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)

    dataset_path = args.dataset or settings.ingest_dataset_path
    if dataset_path is None:
        logger.error("Missing ingestion setting: INGEST_DATASET_PATH")
        return 2
    batch_size = args.batch_size or settings.ingest_batch_size
    if batch_size <= 0:
        logger.error("batch size must be positive")
        return 2
    if args.limit is not None and args.limit <= 0:
        logger.error("limit must be positive")
        return 2
    if args.each and args.limit is None:
        logger.error("--each requires --limit")
        return 2

    try:
        definition = index_definition_from_settings(settings)
        inventory = discover_image_dataset(dataset_path)
        catalog_links = load_catalog_vector_links(args.catalog_manifest)
    except (
        PineconeIndexConfigurationError,
        ImageDatasetError,
        CatalogLinkError,
    ) as exc:
        logger.error("%s", exc)
        return 2

    if not settings.pinecone_namespace:
        logger.error("Missing Pinecone setting: PINECONE_NAMESPACE")
        return 2

    plan = {
        "action": "plan",
        "dataset": str(Path(dataset_path).resolve()),
        "discovered_images": len(inventory.samples),
        "ignored_files": inventory.ignored_file_count,
        "model": settings.clip_model_name,
        "pretrained": settings.clip_pretrained,
        "dimension": definition.dimension,
        "vector_field": definition.vector_field,
        "metadata_fields": [
            "category_id",
            "image_path",
            "product_id",
            "image_id",
        ],
        "catalog_links": len(catalog_links),
        "index": definition.name,
        "namespace": settings.pinecone_namespace,
        "batch_size": batch_size,
        "limit": args.limit,
        "limit_scope": "each_label" if args.each else "global",
        "maximum_images_this_run": (
            args.limit * 42 if args.each and args.limit is not None else args.limit
        ),
    }
    if not args.apply:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        logger.info("Dry run only. Add --apply to embed and upsert images.")
        return 0

    if settings.pinecone_api_key is None:
        logger.error("Missing Pinecone setting: PINECONE_API_KEY")
        return 2

    try:
        client = create_pinecone_client(
            settings.pinecone_api_key.get_secret_value()
        )
        index_status = validate_pinecone_index(client, definition)
        if not index_status.ready:
            logger.error("Pinecone index %r is not ready", definition.name)
            return 1

        index = client.index(definition.name)
        writer = PineconeDocumentRepository(index, settings.pinecone_namespace)
        embedder = OpenClipImageEmbedder(
            model_name=settings.clip_model_name,
            pretrained=settings.clip_pretrained,
            expected_dimension=definition.dimension,
            device=args.device or settings.clip_device,
            cache_dir=settings.clip_cache_dir,
        )
        checkpoint = None
        if not args.no_resume:
            checkpoint_path = args.checkpoint or _default_checkpoint_path(
                definition.name,
                settings.pinecone_namespace,
            )
            checkpoint = IngestionCheckpoint(checkpoint_path)

        stats = ingest_images(
            inventory=inventory,
            embedder=embedder,
            writer=writer,
            vector_field=definition.vector_field,
            batch_size=batch_size,
            checkpoint=checkpoint,
            limit=args.limit,
            each_label=args.each,
            catalog_links=catalog_links,
        )
    except (
        ImageEmbeddingDependencyError,
        ImageEmbeddingError,
        PineconeIndexMismatchError,
        PineconeIndexNotFoundError,
        PineconeSdkUnavailableError,
    ) as exc:
        logger.error("%s", exc)
        return 1
    except Exception:
        logger.exception("Image ingestion failed")
        return 1

    print(json.dumps(asdict(stats), indent=2))
    return 0 if stats.failed == 0 else 1


def _default_checkpoint_path(index_name: str, namespace: str) -> Path:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{index_name}-{namespace}")
    return Path("artifacts") / "ingestion" / f"{safe_name}.checkpoint"


if __name__ == "__main__":
    raise SystemExit(main())
