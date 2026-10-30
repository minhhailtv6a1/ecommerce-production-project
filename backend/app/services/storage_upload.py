"""Validated Supabase Storage uploads for catalog image objects."""

from __future__ import annotations

import csv
import json
import mimetypes
import threading
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, Sequence
from urllib.parse import quote

import httpx

from app.services.image_ingestion import SUPPORTED_IMAGE_EXTENSIONS


REQUIRED_MANIFEST_COLUMNS = frozenset(
    {"id", "product_id", "source_path", "storage_path", "public_url"}
)
RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


class StorageManifestError(ValueError):
    """Raised when the CSV manifest or a source image is invalid."""


class StorageUploadError(RuntimeError):
    """Raised when Supabase rejects or cannot complete an object upload."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        fatal: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.fatal = fatal


class HttpResponse(Protocol):
    status_code: int
    text: str

    def json(self) -> Any: ...


class HttpClient(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        content: bytes,
    ) -> HttpResponse: ...


class StorageSigningHttpClient(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> HttpResponse: ...


@dataclass(frozen=True)
class StorageImage:
    """One local image and its destination object path."""

    image_id: str
    product_id: str
    source_path: str
    source_file: Path
    storage_path: str


@dataclass(frozen=True)
class StorageManifest:
    """Parsed CSV rows plus validated upload objects."""

    path: Path
    fieldnames: tuple[str, ...]
    rows: tuple[dict[str, str], ...]
    images: tuple[StorageImage, ...]


@dataclass(frozen=True)
class StorageUploadResult:
    """Result of one idempotent object upload."""

    storage_path: str
    outcome: str
    public_url: str | None


class StorageUploadCheckpoint:
    """Thread-safe append-only list of completed storage paths."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def load(self) -> set[str]:
        if not self.path.exists():
            return set()
        return {
            line.strip()
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    def append(self, storage_path: str) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(f"{storage_path}\n")


class SupabaseStorageUploader:
    """Small Storage REST client supporting new and legacy server keys."""

    def __init__(
        self,
        *,
        supabase_url: str,
        secret_key: str,
        bucket: str,
        bucket_public: bool,
        max_file_bytes: int,
        client: HttpClient,
        max_attempts: int = 3,
    ) -> None:
        if not supabase_url.startswith("https://"):
            raise ValueError("SUPABASE_URL must use https://")
        if not secret_key:
            raise ValueError("SUPABASE_SECRET_KEY must not be blank")
        if not bucket or "/" in bucket or "\\" in bucket:
            raise ValueError("SUPABASE_STORAGE_BUCKET is invalid")
        if max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be positive")
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")

        self.supabase_url = supabase_url.rstrip("/")
        self.secret_key = secret_key
        self.bucket = bucket
        self.bucket_public = bucket_public
        self.max_file_bytes = max_file_bytes
        self.client = client
        self.max_attempts = max_attempts

    def upload(self, image: StorageImage, *, overwrite: bool) -> StorageUploadResult:
        """Upload one object; an existing object is an idempotent success."""
        size = image.source_file.stat().st_size
        if size <= 0:
            raise StorageManifestError(f"Source image is empty: {image.source_file}")
        if size > self.max_file_bytes:
            raise StorageManifestError(
                f"Source image exceeds standard upload limit ({size} > "
                f"{self.max_file_bytes} bytes): {image.source_path}"
            )

        mime_type = mimetypes.guess_type(image.source_file.name)[0]
        if mime_type is None or not mime_type.startswith("image/"):
            raise StorageManifestError(
                f"Cannot determine an image MIME type: {image.source_path}"
            )

        headers = {
            "apikey": self.secret_key,
            "cache-control": "max-age=3600",
            "content-type": mime_type,
            "user-agent": "image-search-backend-storage-ingest/1.0",
            "x-upsert": str(overwrite).lower(),
        }
        # Legacy service_role keys are JWTs. New sb_secret_ keys must only use apikey.
        if self.secret_key.startswith("eyJ"):
            headers["authorization"] = f"Bearer {self.secret_key}"

        upload_url = self._object_url(image.storage_path)
        content = image.source_file.read_bytes()
        last_error: StorageUploadError | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.client.post(
                    upload_url,
                    headers=headers,
                    content=content,
                )
            except httpx.RequestError as exc:
                last_error = StorageUploadError(
                    f"Storage request failed for {image.storage_path}: {exc}",
                )
                if attempt < self.max_attempts:
                    time.sleep(2 ** (attempt - 1))
                    continue
                raise last_error from exc

            if 200 <= response.status_code < 300:
                return StorageUploadResult(
                    storage_path=image.storage_path,
                    outcome="uploaded",
                    public_url=self.public_url(image.storage_path),
                )
            if not overwrite and _is_existing_object_response(response):
                return StorageUploadResult(
                    storage_path=image.storage_path,
                    outcome="already_exists",
                    public_url=self.public_url(image.storage_path),
                )

            detail = _safe_response_detail(response)
            fatal = response.status_code in {401, 403, 404}
            last_error = StorageUploadError(
                f"Storage upload rejected for {image.storage_path} "
                f"(HTTP {response.status_code}): {detail}",
                status_code=response.status_code,
                fatal=fatal,
            )
            if (
                response.status_code in RETRYABLE_STATUS_CODES
                and attempt < self.max_attempts
            ):
                time.sleep(2 ** (attempt - 1))
                continue
            raise last_error

        assert last_error is not None
        raise last_error

    def public_url(self, storage_path: str) -> str | None:
        """Return a browser URL only when the configured bucket is public."""
        if not self.bucket_public:
            return None
        return (
            f"{self.supabase_url}/storage/v1/object/public/"
            f"{quote(self.bucket, safe='')}/{_encode_object_path(storage_path)}"
        )

    def _object_url(self, storage_path: str) -> str:
        return (
            f"{self.supabase_url}/storage/v1/object/"
            f"{quote(self.bucket, safe='')}/{_encode_object_path(storage_path)}"
        )


class SupabaseStorageUrlResolver:
    """Resolve object paths to public or time-limited browser URLs."""

    def __init__(
        self,
        *,
        supabase_url: str,
        secret_key: str,
        bucket: str,
        bucket_public: bool,
        signed_url_ttl_seconds: int,
        client: StorageSigningHttpClient,
    ) -> None:
        if not supabase_url.startswith("https://"):
            raise ValueError("SUPABASE_URL must use https://")
        if not secret_key:
            raise ValueError("SUPABASE_SECRET_KEY must not be blank")
        if not bucket or "/" in bucket or "\\" in bucket:
            raise ValueError("SUPABASE_STORAGE_BUCKET is invalid")
        if signed_url_ttl_seconds <= 0:
            raise ValueError("signed_url_ttl_seconds must be positive")
        self.supabase_url = supabase_url.rstrip("/")
        self.secret_key = secret_key
        self.bucket = bucket
        self.bucket_public = bucket_public
        self.signed_url_ttl_seconds = signed_url_ttl_seconds
        self.client = client

    def resolve_many(self, storage_paths: Sequence[str]) -> dict[str, str]:
        """Resolve unique object paths with one Storage request for private data."""
        paths = tuple(dict.fromkeys(storage_paths))
        if not paths:
            return {}
        for index, path in enumerate(paths, start=1):
            _validate_relative_path(path, field="storage_path", row_number=index)

        if self.bucket_public:
            return {path: self._public_url(path) for path in paths}

        headers = {
            "apikey": self.secret_key,
            "content-type": "application/json",
            "user-agent": "image-search-backend-api/1.0",
        }
        if self.secret_key.startswith("eyJ"):
            headers["authorization"] = f"Bearer {self.secret_key}"
        url = (
            f"{self.supabase_url}/storage/v1/object/sign/"
            f"{quote(self.bucket, safe='')}"
        )
        try:
            response = self.client.post(
                url,
                headers=headers,
                json={
                    "expiresIn": self.signed_url_ttl_seconds,
                    "paths": list(paths),
                },
            )
        except httpx.RequestError as exc:
            raise StorageUploadError("Unable to create product image URLs") from exc
        if not 200 <= response.status_code < 300:
            raise StorageUploadError(
                "Storage URL signing failed "
                f"(HTTP {response.status_code}): {_safe_response_detail(response)}",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise StorageUploadError("Storage URL signing returned invalid JSON") from exc
        if not isinstance(payload, list):
            raise StorageUploadError("Storage URL signing returned an invalid payload")

        resolved: dict[str, str] = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            signed_url = item.get("signedURL") or item.get("signedUrl")
            if path in paths and isinstance(signed_url, str) and signed_url:
                resolved[path] = self._absolute_signed_url(signed_url)
        missing = [path for path in paths if path not in resolved]
        if missing:
            raise StorageUploadError(
                f"Storage did not sign {len(missing)} requested product images"
            )
        return resolved

    def _public_url(self, storage_path: str) -> str:
        return (
            f"{self.supabase_url}/storage/v1/object/public/"
            f"{quote(self.bucket, safe='')}/{_encode_object_path(storage_path)}"
        )

    def _absolute_signed_url(self, signed_url: str) -> str:
        if signed_url.startswith("https://"):
            return signed_url
        return f"{self.supabase_url}/storage/v1{signed_url}"


def load_storage_manifest(csv_path: Path, dataset_root: Path) -> StorageManifest:
    """Load and validate the product image CSV before any network request."""
    csv_path = csv_path.resolve()
    dataset_root = dataset_root.expanduser().resolve()
    if not csv_path.is_file():
        raise StorageManifestError(f"Image manifest does not exist: {csv_path}")
    if not dataset_root.is_dir():
        raise StorageManifestError(f"Dataset directory does not exist: {dataset_root}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = tuple(reader.fieldnames or ())
        missing = REQUIRED_MANIFEST_COLUMNS - set(fieldnames)
        if missing:
            raise StorageManifestError(
                "Image manifest is missing columns: " + ", ".join(sorted(missing))
            )
        rows = tuple(dict(row) for row in reader)

    images: list[StorageImage] = []
    seen_storage_paths: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        source_path = _validate_relative_path(
            row.get("source_path", ""),
            field="source_path",
            row_number=row_number,
        )
        storage_path = _validate_relative_path(
            row.get("storage_path", ""),
            field="storage_path",
            row_number=row_number,
        )
        expected_storage_path = f"catalog/{source_path}"
        if storage_path != expected_storage_path:
            raise StorageManifestError(
                f"storage_path must be {expected_storage_path!r} at CSV row {row_number}"
            )
        if storage_path in seen_storage_paths:
            raise StorageManifestError(
                f"Duplicate storage_path at CSV row {row_number}: {storage_path}"
            )
        seen_storage_paths.add(storage_path)

        source_file = (dataset_root / Path(*PurePosixPath(source_path).parts)).resolve()
        try:
            source_file.relative_to(dataset_root)
        except ValueError as exc:
            raise StorageManifestError(
                f"Source path escapes dataset root at CSV row {row_number}"
            ) from exc
        if not source_file.is_file():
            raise StorageManifestError(f"Source image is missing: {source_file}")
        if source_file.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            raise StorageManifestError(f"Unsupported image type: {source_path}")

        images.append(
            StorageImage(
                image_id=row.get("id", "").strip(),
                product_id=row.get("product_id", "").strip(),
                source_path=source_path,
                source_file=source_file,
                storage_path=storage_path,
            )
        )

    if not images:
        raise StorageManifestError("Image manifest contains no data rows")
    return StorageManifest(
        path=csv_path,
        fieldnames=fieldnames,
        rows=rows,
        images=tuple(images),
    )


def update_manifest_public_urls(
    manifest: StorageManifest,
    public_urls: dict[str, str],
) -> int:
    """Atomically populate public_url for completed public-bucket objects."""
    if not public_urls:
        return 0
    updated = 0
    rows = [dict(row) for row in manifest.rows]
    for row in rows:
        public_url = public_urls.get(row["storage_path"])
        if public_url is not None and row.get("public_url") != public_url:
            row["public_url"] = public_url
            updated += 1
    if not updated:
        return 0

    temporary_path = manifest.path.with_suffix(manifest.path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=manifest.fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary_path.replace(manifest.path)
    return updated


def _validate_relative_path(value: str, *, field: str, row_number: int) -> str:
    value = value.strip()
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or any("\n" in part or "\r" in part for part in path.parts)
    ):
        raise StorageManifestError(
            f"Invalid {field} at CSV row {row_number}: {value!r}"
        )
    return path.as_posix()


def _encode_object_path(storage_path: str) -> str:
    return "/".join(quote(part, safe="") for part in PurePosixPath(storage_path).parts)


def _is_existing_object_response(response: HttpResponse) -> bool:
    if response.status_code not in {400, 409}:
        return False
    detail = _safe_response_detail(response).lower()
    markers = (
        "already exists",
        "already_exists",
        "keyalreadyexists",
        "resourcealreadyexists",
        "duplicate",
    )
    return any(marker in detail for marker in markers)


def _safe_response_detail(response: HttpResponse) -> str:
    try:
        payload = response.json()
        detail = json.dumps(payload, ensure_ascii=False)
    except (ValueError, TypeError):
        detail = response.text
    detail = detail.replace("\r", " ").replace("\n", " ").strip()
    return detail[:500] or "no response body"

