"""Attach relational catalog identifiers to existing Pinecone documents."""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.repositories.pinecone import (
    PineconeDocumentRepository,
    PineconeSdkUnavailableError,
    create_pinecone_client,
)
from app.services.catalog_links import (
    CatalogLinkError,
    CatalogVectorLink,
    load_catalog_vector_links,
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
            "Partially update existing Pinecone documents with product_id and "
            "image_id from data/product_images.csv. Vector values are unchanged."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write metadata to Pinecone. The default is a local dry run.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Read and verify all manifest links without submitting updates.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/product_images.csv"),
        help="Catalog product-image manifest.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Documents per Pinecone update/fetch request (default: 100).",
    )
    parser.add_argument(
        "--verify-retries",
        type=int,
        default=5,
        help="Verification attempts for Pinecone's asynchronous update.",
    )
    parser.add_argument(
        "--verify-delay",
        type=float,
        default=2.0,
        help="Seconds between verification attempts.",
    )
    return parser


def build_metadata_patches(
    links: Mapping[str, CatalogVectorLink],
) -> list[dict[str, str]]:
    """Build deterministic per-document partial updates."""
    return [
        {
            "_id": vector_id,
            "product_id": link.product_id,
            "image_id": link.image_id,
        }
        for vector_id, link in sorted(links.items())
    ]


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)
    if args.apply and args.verify_only:
        logger.error("--apply and --verify-only are mutually exclusive")
        return 2
    if args.batch_size <= 0 or args.batch_size > 100:
        logger.error("--batch-size must be between 1 and 100")
        return 2
    if args.verify_retries <= 0 or args.verify_delay < 0:
        logger.error("verification options must be non-negative and retries positive")
        return 2

    try:
        links = load_catalog_vector_links(args.manifest)
        definition = index_definition_from_settings(settings)
    except (CatalogLinkError, PineconeIndexConfigurationError) as exc:
        logger.error("%s", exc)
        return 2

    plan = {
        "action": (
            "apply" if args.apply else "verify" if args.verify_only else "plan"
        ),
        "manifest": str(args.manifest.resolve()),
        "documents": len(links),
        "fields": ["product_id", "image_id"],
        "index": definition.name,
        "namespace": settings.pinecone_namespace,
        "vectors_recomputed": False,
    }
    if not args.apply and not args.verify_only:
        print(json.dumps(plan, indent=2))
        logger.info("Dry run only. Add --apply to update Pinecone metadata.")
        return 0

    if settings.pinecone_api_key is None or not settings.pinecone_namespace:
        logger.error("PINECONE_API_KEY and PINECONE_NAMESPACE are required")
        return 2

    try:
        client = create_pinecone_client(
            settings.pinecone_api_key.get_secret_value()
        )
        status = validate_pinecone_index(client, definition)
        if not status.ready:
            logger.error("Pinecone index %r is not ready", definition.name)
            return 1
        repository = PineconeDocumentRepository(
            client.index(definition.name),
            settings.pinecone_namespace,
        )
        if args.apply:
            patches = build_metadata_patches(links)
            for offset in range(0, len(patches), args.batch_size):
                repository.update_fields(patches[offset : offset + args.batch_size])
                logger.info(
                    "Accepted metadata updates: %d/%d",
                    min(offset + args.batch_size, len(patches)),
                    len(patches),
                )

        remaining = dict(links)
        for attempt in range(1, args.verify_retries + 1):
            if args.verify_delay:
                time.sleep(args.verify_delay)
            remaining = _find_unverified_links(
                repository,
                remaining,
                batch_size=args.batch_size,
            )
            if not remaining:
                break
            logger.info(
                "Verification attempt %d/%d: %d documents pending",
                attempt,
                args.verify_retries,
                len(remaining),
            )
    except (
        PineconeIndexMismatchError,
        PineconeIndexNotFoundError,
        PineconeSdkUnavailableError,
    ) as exc:
        logger.error("%s", exc)
        return 1
    except Exception:
        logger.exception("Pinecone catalog metadata backfill failed")
        return 1

    if remaining:
        logger.error(
            "Metadata verification failed for %d/%d documents",
            len(remaining),
            len(links),
        )
        return 1

    print(json.dumps({**plan, "verified": len(links)}, indent=2))
    return 0


def _find_unverified_links(
    repository: PineconeDocumentRepository,
    links: Mapping[str, CatalogVectorLink],
    *,
    batch_size: int,
) -> dict[str, CatalogVectorLink]:
    remaining: dict[str, CatalogVectorLink] = {}
    ids = list(links)
    for offset in range(0, len(ids), batch_size):
        batch_ids = ids[offset : offset + batch_size]
        fetched = repository.fetch_fields(
            batch_ids,
            include_fields=("product_id", "image_id"),
        )
        actual = {_document_id(document): document for document in fetched}
        for vector_id in batch_ids:
            document = actual.get(vector_id)
            expected = links[vector_id]
            if document is None or (
                _document_field(document, "product_id") != expected.product_id
                or _document_field(document, "image_id") != expected.image_id
            ):
                remaining[vector_id] = expected
    return remaining


def _document_id(document: Any) -> str:
    value = _document_field(document, "_id") or _document_field(document, "id")
    return str(value or "")


def _document_field(document: Any, name: str) -> Any:
    if isinstance(document, Mapping):
        return document.get(name)
    return getattr(document, name, None)


if __name__ == "__main__":
    raise SystemExit(main())
