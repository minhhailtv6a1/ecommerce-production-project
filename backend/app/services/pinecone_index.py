"""Idempotent Pinecone index provisioning logic."""

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from app.core.config import Settings


PineconeMetric = Literal["cosine", "euclidean", "dotproduct"]
DeletionProtection = Literal["enabled", "disabled"]


class PineconeIndexConfigurationError(ValueError):
    """Raised when required index configuration is missing or invalid."""


class PineconeIndexMismatchError(RuntimeError):
    """Raised when an existing index is incompatible with the requested schema."""


class PineconeIndexNotFoundError(RuntimeError):
    """Raised when ingestion targets an index that does not exist."""


@dataclass(frozen=True)
class PineconeIndexDefinition:
    """Immutable definition of the dense-vector index to provision."""

    name: str
    vector_field: str
    dimension: int
    metric: PineconeMetric
    cloud: str
    region: str
    deletion_protection: DeletionProtection
    timeout: int

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "fields": {
                self.vector_field: {
                    "type": "dense_vector",
                    "dimension": self.dimension,
                    "metric": self.metric,
                }
            }
        }

    @property
    def deployment(self) -> dict[str, str]:
        return {
            "deployment_type": "managed",
            "cloud": self.cloud,
            "region": self.region,
        }


@dataclass(frozen=True)
class PineconeIndexProvisionResult:
    """Outcome of ensuring that the configured index exists."""

    action: Literal["created", "existing"]
    name: str
    ready: bool
    host: str | None


def index_definition_from_settings(settings: Settings) -> PineconeIndexDefinition:
    """Build a validated index definition from application settings."""
    required_values = {
        "PINECONE_INDEX_NAME": settings.pinecone_index_name,
        "PINECONE_VECTOR_FIELD": settings.pinecone_vector_field,
        "PINECONE_DIMENSION": settings.pinecone_dimension,
        "PINECONE_METRIC": settings.pinecone_metric,
        "PINECONE_CLOUD": settings.pinecone_cloud,
        "PINECONE_REGION": settings.pinecone_region,
    }
    missing = [
        name
        for name, value in required_values.items()
        if value is None or (isinstance(value, str) and not value.strip())
    ]
    if missing:
        raise PineconeIndexConfigurationError(
            "Missing Pinecone index settings: " + ", ".join(missing)
        )

    return PineconeIndexDefinition(
        name=str(settings.pinecone_index_name).strip(),
        vector_field=str(settings.pinecone_vector_field).strip(),
        dimension=int(settings.pinecone_dimension),
        metric=settings.pinecone_metric,
        cloud=str(settings.pinecone_cloud).strip(),
        region=str(settings.pinecone_region).strip(),
        deletion_protection=settings.pinecone_deletion_protection,
        timeout=settings.pinecone_create_timeout,
    )


def ensure_pinecone_index(
    client: Any,
    definition: PineconeIndexDefinition,
) -> PineconeIndexProvisionResult:
    """Create the index once or validate an existing index for compatibility."""
    if client.indexes.exists(definition.name):
        description = client.indexes.describe(definition.name)
        _validate_existing_index(description, definition)
        return _result_from_description("existing", definition.name, description)

    description = client.indexes.create(
        name=definition.name,
        schema=definition.schema,
        deployment=definition.deployment,
        deletion_protection=definition.deletion_protection,
        timeout=definition.timeout,
    )
    return _result_from_description("created", definition.name, description)


def validate_pinecone_index(
    client: Any,
    definition: PineconeIndexDefinition,
) -> PineconeIndexProvisionResult:
    """Validate an existing index without creating or changing cloud resources."""
    if not client.indexes.exists(definition.name):
        raise PineconeIndexNotFoundError(
            f"Pinecone index {definition.name!r} does not exist"
        )
    description = client.indexes.describe(definition.name)
    _validate_existing_index(description, definition)
    return _result_from_description("existing", definition.name, description)


def _validate_existing_index(
    description: Any,
    definition: PineconeIndexDefinition,
) -> None:
    schema = _read_value(description, "schema")
    fields = _read_value(schema, "fields")
    vector_field = _read_value(fields, definition.vector_field)
    deployment = _read_value(description, "deployment")

    actual = {
        "vector field": definition.vector_field if vector_field is not None else None,
        "dimension": _read_value(vector_field, "dimension"),
        "metric": _enum_value(_read_value(vector_field, "metric")),
        "cloud": _enum_value(_read_value(deployment, "cloud")),
        "region": _enum_value(_read_value(deployment, "region")),
    }
    expected = {
        "vector field": definition.vector_field,
        "dimension": definition.dimension,
        "metric": definition.metric,
        "cloud": definition.cloud,
        "region": definition.region,
    }
    mismatches = [
        f"{key}: expected {expected[key]!r}, found {actual[key]!r}"
        for key in expected
        if actual[key] != expected[key]
    ]
    if mismatches:
        raise PineconeIndexMismatchError(
            f"Pinecone index {definition.name!r} has an incompatible definition: "
            + "; ".join(mismatches)
        )


def _result_from_description(
    action: Literal["created", "existing"],
    name: str,
    description: Any,
) -> PineconeIndexProvisionResult:
    status = _read_value(description, "status")
    return PineconeIndexProvisionResult(
        action=action,
        name=name,
        ready=bool(_read_value(status, "ready")),
        host=_read_value(description, "host"),
    )


def _read_value(container: Any, key: str) -> Any:
    if container is None:
        return None
    if isinstance(container, Mapping):
        return container.get(key)
    return getattr(container, key, None)


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)
