import csv
import shutil
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest

from app.services.storage_upload import (
    StorageManifestError,
    SupabaseStorageUploader,
    load_storage_manifest,
    update_manifest_public_urls,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, str]) -> None:
        self.status_code = status_code
        self.payload = payload
        self.text = str(payload)

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls = []

    def post(self, url: str, *, headers: dict[str, str], content: bytes):
        self.calls.append({"url": url, "headers": headers, "content": content})
        return self.responses.pop(0)


@contextmanager
def _writable_test_directory():
    root = Path.cwd() / f"pytest-cache-files-storage-{uuid4().hex}"
    root.mkdir()
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _manifest(root: Path, source_path: str = "00/example image.jpg"):
    dataset = root / "dataset"
    source_file = dataset / Path(*source_path.split("/"))
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"fake-jpeg-content")
    csv_path = root / "product_images.csv"
    fieldnames = (
        "id",
        "product_id",
        "source_path",
        "storage_path",
        "public_url",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "id": "image-id",
                "product_id": "product-id",
                "source_path": source_path,
                "storage_path": f"catalog/{source_path}",
                "public_url": "",
            }
        )
    return load_storage_manifest(csv_path, dataset)


def test_upload_uses_secret_key_header_and_generates_public_url() -> None:
    with _writable_test_directory() as root:
        manifest = _manifest(root)
        client = FakeClient([FakeResponse(200, {"Key": "object-key"})])
        uploader = SupabaseStorageUploader(
            supabase_url="https://project.supabase.co/",
            secret_key="sb_secret_test",
            bucket="product-images",
            bucket_public=True,
            max_file_bytes=1024,
            client=client,
        )

        result = uploader.upload(manifest.images[0], overwrite=False)

        assert result.outcome == "uploaded"
        assert result.public_url == (
            "https://project.supabase.co/storage/v1/object/public/"
            "product-images/catalog/00/example%20image.jpg"
        )
        call = client.calls[0]
        assert call["url"].endswith(
            "/storage/v1/object/product-images/catalog/00/example%20image.jpg"
        )
        assert call["headers"]["apikey"] == "sb_secret_test"
        assert "authorization" not in call["headers"]
        assert call["headers"]["x-upsert"] == "false"
        assert call["headers"]["content-type"] == "image/jpeg"
        assert call["content"] == b"fake-jpeg-content"


def test_existing_object_is_idempotent_and_legacy_key_uses_bearer() -> None:
    with _writable_test_directory() as root:
        manifest = _manifest(root)
        client = FakeClient(
            [FakeResponse(409, {"code": "KeyAlreadyExists", "message": "exists"})]
        )
        uploader = SupabaseStorageUploader(
            supabase_url="https://project.supabase.co",
            secret_key="eyJlegacy-service-role",
            bucket="product-images",
            bucket_public=False,
            max_file_bytes=1024,
            client=client,
        )

        result = uploader.upload(manifest.images[0], overwrite=False)

        assert result.outcome == "already_exists"
        assert result.public_url is None
        assert client.calls[0]["headers"]["authorization"] == (
            "Bearer eyJlegacy-service-role"
        )


def test_manifest_public_url_update_is_atomic() -> None:
    with _writable_test_directory() as root:
        manifest = _manifest(root)
        storage_path = manifest.images[0].storage_path

        updated = update_manifest_public_urls(
            manifest,
            {storage_path: "https://images.example.test/catalog/00/example.jpg"},
        )

        assert updated == 1
        with manifest.path.open(encoding="utf-8", newline="") as stream:
            row = next(csv.DictReader(stream))
        assert row["public_url"] == (
            "https://images.example.test/catalog/00/example.jpg"
        )


def test_manifest_rejects_storage_path_outside_catalog_layout() -> None:
    with _writable_test_directory() as root:
        manifest = _manifest(root)
        with manifest.path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        rows[0]["storage_path"] = "other/example.jpg"
        with manifest.path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=manifest.fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        with pytest.raises(StorageManifestError, match="storage_path must be"):
            load_storage_manifest(manifest.path, root / "dataset")

