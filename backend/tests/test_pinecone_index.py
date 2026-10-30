"""Unit tests for Pinecone index provisioning."""

from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import Settings
from app.services.pinecone_index import (
    PineconeIndexConfigurationError,
    PineconeIndexDefinition,
    PineconeIndexMismatchError,
    PineconeIndexNotFoundError,
    ensure_pinecone_index,
    index_definition_from_settings,
    validate_pinecone_index,
)


def make_definition() -> PineconeIndexDefinition:
    return PineconeIndexDefinition(
        name="product-images",
        vector_field="embedding",
        dimension=512,
        metric="cosine",
        cloud="aws",
        region="us-east-1",
        deletion_protection="enabled",
        timeout=300,
    )


def make_description(
    *, dimension: int = 512, metric: str = "cosine"
) -> SimpleNamespace:
    return SimpleNamespace(
        host="product-images.example.pinecone.io",
        status=SimpleNamespace(ready=True),
        schema=SimpleNamespace(
            fields={
                "embedding": SimpleNamespace(
                    dimension=dimension,
                    metric=metric,
                )
            }
        ),
        deployment=SimpleNamespace(cloud="aws", region="us-east-1"),
    )


class FakeIndexes:
    def __init__(self, *, exists: bool, description: Any) -> None:
        self._exists = exists
        self._description = description
        self.create_calls: list[dict[str, Any]] = []

    def exists(self, name: str) -> bool:
        return self._exists

    def describe(self, name: str) -> Any:
        return self._description

    def create(self, **kwargs: Any) -> Any:
        self.create_calls.append(kwargs)
        return self._description


def test_index_definition_reports_missing_settings() -> None:
    empty_settings = Settings(
        _env_file=None,
        pinecone_index_name=None,
        pinecone_vector_field=None,
        pinecone_dimension=None,
        pinecone_metric=None,
        pinecone_cloud=None,
        pinecone_region=None,
    )

    with pytest.raises(PineconeIndexConfigurationError) as exc_info:
        index_definition_from_settings(empty_settings)

    assert "PINECONE_DIMENSION" in str(exc_info.value)
    assert "PINECONE_REGION" in str(exc_info.value)


def test_ensure_index_creates_expected_serverless_schema() -> None:
    indexes = FakeIndexes(exists=False, description=make_description())
    client = SimpleNamespace(indexes=indexes)

    result = ensure_pinecone_index(client, make_definition())

    assert result.action == "created"
    assert result.ready is True
    assert indexes.create_calls == [
        {
            "name": "product-images",
            "schema": {
                "fields": {
                    "embedding": {
                        "type": "dense_vector",
                        "dimension": 512,
                        "metric": "cosine",
                    }
                }
            },
            "deployment": {
                "deployment_type": "managed",
                "cloud": "aws",
                "region": "us-east-1",
            },
            "deletion_protection": "enabled",
            "timeout": 300,
        }
    ]


def test_ensure_index_reuses_compatible_existing_index() -> None:
    indexes = FakeIndexes(exists=True, description=make_description())
    client = SimpleNamespace(indexes=indexes)

    result = ensure_pinecone_index(client, make_definition())

    assert result.action == "existing"
    assert result.ready is True
    assert indexes.create_calls == []


def test_ensure_index_rejects_incompatible_existing_index() -> None:
    indexes = FakeIndexes(
        exists=True,
        description=make_description(dimension=768),
    )
    client = SimpleNamespace(indexes=indexes)

    with pytest.raises(PineconeIndexMismatchError, match="dimension"):
        ensure_pinecone_index(client, make_definition())


def test_validate_index_does_not_create_missing_index() -> None:
    indexes = FakeIndexes(exists=False, description=make_description())
    client = SimpleNamespace(indexes=indexes)

    with pytest.raises(PineconeIndexNotFoundError):
        validate_pinecone_index(client, make_definition())

    assert indexes.create_calls == []
