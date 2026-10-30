"""Opt-in live verification of Pinecone index provisioning."""

import os

import pytest

from app.core.config import settings
from app.repositories.pinecone import create_pinecone_client
from app.services.pinecone_index import (
    ensure_pinecone_index,
    index_definition_from_settings,
)


@pytest.mark.integration
def test_live_pinecone_index_is_ready() -> None:
    if os.getenv("RUN_PINECONE_INTEGRATION") != "1":
        pytest.skip("Set RUN_PINECONE_INTEGRATION=1 to allow Pinecone API calls")
    if settings.pinecone_api_key is None:
        pytest.fail("PINECONE_API_KEY is required for the live integration test")

    definition = index_definition_from_settings(settings)
    client = create_pinecone_client(settings.pinecone_api_key.get_secret_value())

    result = ensure_pinecone_index(client, definition)

    assert result.ready is True
