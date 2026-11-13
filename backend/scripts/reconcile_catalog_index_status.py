"""Reconcile PostgreSQL image index state with verified Pinecone documents."""

from __future__ import annotations

import argparse
import csv
import json
import logging
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from app.core.config import settings
from app.repositories.database import open_database_connection
from app.repositories.pinecone import PineconeDocumentRepository, create_pinecone_client
from app.services.catalog_links import load_catalog_vector_links
from app.services.pinecone_index import index_definition_from_settings, validate_pinecone_index
from scripts.backfill_pinecone_catalog_metadata import _find_unverified_links


logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify catalog links in Pinecone, then mark matching DB images indexed."
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/product_images.csv"),
    )
    parser.add_argument("--batch-size", type=int, default=100)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)
    if args.batch_size <= 0 or args.batch_size > 100:
        logger.error("--batch-size must be between 1 and 100")
        return 2

    links = load_catalog_vector_links(args.manifest)
    plan = {
        "action": "apply" if args.apply else "plan",
        "manifest": str(args.manifest.resolve()),
        "documents": len(links),
        "database_change": "verified matching rows -> indexed",
    }
    if not args.apply:
        print(json.dumps(plan, indent=2))
        return 0
    if settings.pinecone_api_key is None or not settings.pinecone_namespace:
        logger.error("PINECONE_API_KEY and PINECONE_NAMESPACE are required")
        return 2

    definition = index_definition_from_settings(settings)
    client = create_pinecone_client(settings.pinecone_api_key.get_secret_value())
    status = validate_pinecone_index(client, definition)
    if not status.ready:
        logger.error("Pinecone index is not ready")
        return 1
    repository = PineconeDocumentRepository(
        client.index(definition.name),
        settings.pinecone_namespace,
    )
    unverified = _find_unverified_links(repository, links, batch_size=args.batch_size)
    if unverified:
        logger.error("Refusing database update: %d documents are unverified", len(unverified))
        return 1

    with args.manifest.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    parameters = [
        (row["pinecone_vector_id"], UUID(row["product_id"]), UUID(row["id"]))
        for row in rows
    ]
    connection = open_database_connection()
    try:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                UPDATE public.product_images
                SET index_status = 'indexed',
                    indexed_at = COALESCE(indexed_at, CURRENT_TIMESTAMP),
                    index_error = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE pinecone_vector_id = %s
                  AND product_id = %s
                  AND id = %s
                  AND index_status <> 'removed'
                """,
                parameters,
            )
            cursor.execute(
                """
                SELECT index_status, COUNT(*)
                FROM public.product_images
                GROUP BY index_status ORDER BY index_status
                """
            )
            distribution = cursor.fetchall()
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(json.dumps({**plan, "verified": len(links), "status": distribution}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
