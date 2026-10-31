"""Regression tests for index-friendly catalog SQL."""

from typing import Any
from uuid import UUID

from app.repositories.products import ProductFilters, ProductRepository


PRODUCT_ID = UUID("d876766d-3552-5916-80ef-54658aace46b")


class RecordingCursor:
    def __init__(self, connection: "RecordingConnection") -> None:
        self.connection = connection

    def __enter__(self) -> "RecordingCursor":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def execute(self, sql: str, params: Any) -> None:
        self.connection.calls.append((sql, params))

    def fetchall(self) -> list[dict[str, Any]]:
        return self.connection.fetchall_results.pop(0)

    def fetchone(self) -> dict[str, Any] | None:
        return self.connection.fetchone_results.pop(0)


class RecordingConnection:
    def __init__(
        self,
        *fetchone_results: dict[str, Any] | None,
        fetchall_results: list[list[dict[str, Any]]] | None = None,
    ) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.fetchone_results = list(fetchone_results)
        self.fetchall_results = fetchall_results or []

    def cursor(self, **kwargs: Any) -> RecordingCursor:
        return RecordingCursor(self)


def test_bulk_hydration_uses_native_uuid_parameters() -> None:
    connection = RecordingConnection(fetchall_results=[[], [], []])
    repository = ProductRepository(connection)

    repository.get_products_by_ids([str(PRODUCT_ID), "stale-pinecone-id"])
    repository.get_variants([str(PRODUCT_ID)])
    repository.get_images([str(PRODUCT_ID)])

    assert len(connection.calls) == 3
    for sql, params in connection.calls:
        assert "::text" not in sql
        assert params == [[PRODUCT_ID]]


def test_product_lookup_uses_separate_primary_key_and_slug_queries() -> None:
    connection = RecordingConnection(None, None)
    repository = ProductRepository(connection)

    repository.get_product(str(PRODUCT_ID))
    repository.get_product("dam-vay-nu-001")

    uuid_sql, uuid_params = connection.calls[0]
    slug_sql, slug_params = connection.calls[1]
    assert "p.id = %s" in uuid_sql
    assert uuid_params == [PRODUCT_ID]
    assert "p.slug = %s" in slug_sql
    assert slug_params == ["dam-vay-nu-001"]


def test_newest_catalog_pages_before_variant_aggregation() -> None:
    connection = RecordingConnection(
        fetchall_results=[[{"id": PRODUCT_ID, "_total": 8400}]]
    )
    repository = ProductRepository(connection)

    rows, total = repository.list_products(ProductFilters(page=2, page_size=20))

    assert rows == [{"id": PRODUCT_ID}]
    assert total == 8400
    page_sql, page_params = connection.calls[0]
    assert "WITH product_page AS" in page_sql
    assert page_sql.index("LIMIT %s OFFSET %s") < page_sql.index("MIN(v.price)")
    assert "COUNT(*) OVER()" in page_sql
    assert page_params == [20, 20]


def test_price_sort_keeps_aggregate_before_pagination() -> None:
    connection = RecordingConnection(
        fetchall_results=[[{"id": PRODUCT_ID, "_total": 8400}]]
    )
    repository = ProductRepository(connection)

    repository.list_products(ProductFilters(sort="price_asc"))

    sql, _ = connection.calls[0]
    assert "WITH product_page AS" not in sql
    assert "ORDER BY price ASC" in sql


def test_out_of_range_page_falls_back_to_count_query() -> None:
    connection = RecordingConnection(
        {"total": 8400},
        fetchall_results=[[]],
    )
    repository = ProductRepository(connection)

    rows, total = repository.list_products(ProductFilters(page=999))

    assert rows == []
    assert total == 8400
    assert len(connection.calls) == 2

