"""Tests for browser-safe Supabase Storage URL resolution."""

from typing import Any

from app.services.storage_upload import SupabaseStorageUrlResolver


class FakeResponse:
    status_code = 200
    text = ""

    def json(self) -> Any:
        return [
            {
                "path": "catalog/00/a.jpg",
                "signedURL": "/object/sign/products/catalog/00/a.jpg?token=x",
            }
        ]


class FakeSigningClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return FakeResponse()


def test_private_bucket_uses_one_bulk_signed_url_request() -> None:
    client = FakeSigningClient()
    resolver = SupabaseStorageUrlResolver(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        bucket="products",
        bucket_public=False,
        signed_url_ttl_seconds=3600,
        client=client,
    )

    result = resolver.resolve_many(["catalog/00/a.jpg", "catalog/00/a.jpg"])

    assert result == {
        "catalog/00/a.jpg": (
            "https://project.supabase.co/storage/v1/object/sign/"
            "products/catalog/00/a.jpg?token=x"
        )
    }
    assert client.calls[0]["json"] == {
        "expiresIn": 3600,
        "paths": ["catalog/00/a.jpg"],
    }
    assert "authorization" not in client.calls[0]["headers"]


def test_public_bucket_builds_urls_without_http_request() -> None:
    client = FakeSigningClient()
    resolver = SupabaseStorageUrlResolver(
        supabase_url="https://project.supabase.co",
        secret_key="sb_secret_test",
        bucket="products",
        bucket_public=True,
        signed_url_ttl_seconds=3600,
        client=client,
    )

    result = resolver.resolve_many(["catalog/00/a b.jpg"])

    assert result["catalog/00/a b.jpg"].endswith(
        "/object/public/products/catalog/00/a%20b.jpg"
    )
    assert client.calls == []
