"""Embed one test image and search similar indexed images in Pinecone."""

import argparse
import json
import logging
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
    ImageEmbeddingDependencyError,
    ImageEmbeddingError,
    OpenClipImageEmbedder,
)
from app.services.image_search import (
    QueryImageError,
    search_similar_images,
    select_query_image,
    validate_query_image,
)
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
            "Embed one test image with OpenAI CLIP ViT-B-32 and retrieve "
            "visually similar Pinecone documents."
        )
    )
    parser.add_argument(
        "--image",
        type=Path,
        default=None,
        help="Use this exact query image instead of selecting one from the test folder.",
    )
    parser.add_argument(
        "--test-dir",
        type=Path,
        default=None,
        help="Override SEARCH_TEST_DATASET_PATH for automatic image selection.",
    )
    parser.add_argument(
        "--random",
        action="store_true",
        help="Choose a random image recursively from the test folder.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Make --random selection reproducible.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of nearest images to return (default: 10).",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help="Restrict search to a canonical category ID; repeat for multiple IDs.",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda"),
        default=None,
        help="Override CLIP_DEVICE for this run.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)

    if args.top_k <= 0:
        logger.error("--top-k must be positive")
        return 2
    if args.image is not None and (args.random or args.seed is not None):
        logger.error("--random and --seed cannot be combined with --image")
        return 2
    if args.seed is not None and not args.random:
        logger.error("--seed requires --random")
        return 2

    try:
        query_image = _resolve_query_image(args)
        definition = index_definition_from_settings(settings)
    except (QueryImageError, PineconeIndexConfigurationError) as exc:
        logger.error("%s", exc)
        return 2

    if settings.pinecone_api_key is None:
        logger.error("Missing Pinecone setting: PINECONE_API_KEY")
        return 2
    if not settings.pinecone_namespace:
        logger.error("Missing Pinecone setting: PINECONE_NAMESPACE")
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
        searcher = PineconeDocumentRepository(
            index,
            settings.pinecone_namespace,
        )
        embedder = OpenClipImageEmbedder(
            model_name=settings.clip_model_name,
            pretrained=settings.clip_pretrained,
            expected_dimension=definition.dimension,
            device=args.device or settings.clip_device,
            cache_dir=settings.clip_cache_dir,
        )
        matches = search_similar_images(
            query_image=query_image,
            embedder=embedder,
            searcher=searcher,
            vector_field=definition.vector_field,
            top_k=args.top_k,
            category_ids=args.category,
        )
    except (
        ImageEmbeddingDependencyError,
        ImageEmbeddingError,
        PineconeIndexMismatchError,
        PineconeIndexNotFoundError,
        PineconeSdkUnavailableError,
        QueryImageError,
    ) as exc:
        logger.error("%s", exc)
        return 1
    except Exception:
        logger.exception("Image search failed")
        return 1

    result = {
        "query_image": str(query_image),
        "model": settings.clip_model_name,
        "pretrained": settings.clip_pretrained,
        "index": definition.name,
        "namespace": settings.pinecone_namespace,
        "top_k": args.top_k,
        "category_filter": args.category,
        "matches": [
            {"rank": rank, **asdict(match)}
            for rank, match in enumerate(matches, start=1)
        ],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _resolve_query_image(args: argparse.Namespace) -> Path:
    if args.image is not None:
        return validate_query_image(args.image)

    test_dir = args.test_dir or settings.search_test_dataset_path
    if test_dir is None and settings.ingest_dataset_path is not None:
        test_dir = settings.ingest_dataset_path.parent / "test"
    if test_dir is None:
        raise QueryImageError(
            "Missing query-image directory: set SEARCH_TEST_DATASET_PATH "
            "or pass --test-dir/--image"
        )
    return select_query_image(
        test_dir,
        randomize=args.random,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
