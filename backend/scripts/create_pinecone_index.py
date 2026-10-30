"""Plan or apply creation of the configured Pinecone index."""

import argparse
import json
import logging
from collections.abc import Sequence

from app.core.config import settings
from app.repositories.pinecone import (
    PineconeSdkUnavailableError,
    create_pinecone_client,
)
from app.services.pinecone_index import (
    PineconeIndexConfigurationError,
    PineconeIndexMismatchError,
    ensure_pinecone_index,
    index_definition_from_settings,
)


logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or validate the configured Pinecone serverless index."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the Pinecone API call. Without this flag, only print the plan.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)

    try:
        definition = index_definition_from_settings(settings)
    except PineconeIndexConfigurationError as exc:
        logger.error("%s", exc)
        return 2

    plan = {
        "name": definition.name,
        "schema": definition.schema,
        "deployment": definition.deployment,
        "deletion_protection": definition.deletion_protection,
        "timeout": definition.timeout,
    }
    if not args.apply:
        print(json.dumps({"action": "plan", **plan}, indent=2))
        logger.info("Dry run only. Add --apply to create or validate the index.")
        return 0

    if settings.pinecone_api_key is None:
        logger.error("Missing Pinecone setting: PINECONE_API_KEY")
        return 2

    try:
        client = create_pinecone_client(
            settings.pinecone_api_key.get_secret_value()
        )
        result = ensure_pinecone_index(client, definition)
    except (PineconeSdkUnavailableError, PineconeIndexMismatchError) as exc:
        logger.error("%s", exc)
        return 1
    except Exception:
        logger.exception("Pinecone index provisioning failed")
        return 1

    print(
        json.dumps(
            {
                "action": result.action,
                "name": result.name,
                "ready": result.ready,
                "host": result.host,
            },
            indent=2,
        )
    )
    return 0 if result.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
