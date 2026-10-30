"""Upload catalog images to Supabase Storage from product_images.csv."""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

from app.core.categories import CANONICAL_CATEGORY_IDS
from app.core.config import settings
from app.services.storage_upload import (
    StorageImage,
    StorageManifestError,
    StorageUploadCheckpoint,
    StorageUploadError,
    SupabaseStorageUploader,
    load_storage_manifest,
    update_manifest_public_urls,
)


logger = logging.getLogger(__name__)
DEFAULT_MANIFEST_PATH = Path("data/product_images.csv")


@dataclass(frozen=True)
class UploadStats:
    selected: int
    pending: int
    uploaded: int
    already_exists: int
    skipped_checkpoint: int
    failed: int
    public_urls_updated: int
    aborted_early: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Upload catalog images to the configured Supabase Storage bucket "
            "using storage_path values such as catalog/00/image.jpg."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform network uploads. The default is a validated dry run.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to product_images.csv.",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="Override INGEST_DATASET_PATH.",
    )
    parser.add_argument(
        "--category",
        action="append",
        dest="categories",
        help="Upload only one canonical category; repeat for multiple categories.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most this many selected images, useful for a smoke test.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Concurrent uploads (default: SUPABASE_STORAGE_UPLOAD_WORKERS).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Set x-upsert=true and replace objects at existing paths.",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Override the append-only resume checkpoint path.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore and do not update the local upload checkpoint.",
    )
    parser.add_argument(
        "--no-update-csv",
        action="store_true",
        help="Do not populate public_url in product_images.csv for a public bucket.",
    )
    bucket_group = parser.add_mutually_exclusive_group()
    bucket_group.add_argument(
        "--public-bucket",
        action="store_true",
        help="Treat the bucket as public and generate browser-accessible URLs.",
    )
    bucket_group.add_argument(
        "--private-bucket",
        action="store_true",
        help="Treat the bucket as private and leave public_url unchanged.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)
    dataset = args.dataset or settings.ingest_dataset_path
    workers = args.workers or settings.supabase_storage_upload_workers
    if dataset is None:
        logger.error("Missing dataset path: use --dataset or INGEST_DATASET_PATH")
        return 2
    if args.limit is not None and args.limit <= 0:
        logger.error("--limit must be positive")
        return 2
    if workers <= 0 or workers > 16:
        logger.error("--workers must be between 1 and 16")
        return 2
    categories = tuple(dict.fromkeys(args.categories or ()))
    invalid_categories = sorted(set(categories) - set(CANONICAL_CATEGORY_IDS))
    if invalid_categories:
        logger.error("Unknown category IDs: %s", ", ".join(invalid_categories))
        return 2

    try:
        manifest = load_storage_manifest(args.manifest, dataset)
    except StorageManifestError as exc:
        logger.error("%s", exc)
        return 2

    selected = [
        image
        for image in manifest.images
        if not categories or image.source_path.split("/", 1)[0] in categories
    ]
    if args.limit is not None:
        selected = selected[: args.limit]
    if not selected:
        logger.error("No manifest images match the requested selection")
        return 2

    bucket_public = settings.supabase_storage_bucket_public
    if args.public_bucket:
        bucket_public = True
    elif args.private_bucket:
        bucket_public = False

    plan = {
        "action": "apply" if args.apply else "plan",
        "manifest": str(manifest.path),
        "dataset": str(Path(dataset).resolve()),
        "selected": len(selected),
        "categories": list(categories) if categories else "all",
        "first_object": selected[0].storage_path,
        "last_object": selected[-1].storage_path,
        "bucket": settings.supabase_storage_bucket,
        "bucket_public": bucket_public,
        "workers": workers,
        "overwrite": args.overwrite,
        "resume": not args.no_resume,
        "update_csv_public_urls": bucket_public and not args.no_update_csv,
    }
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        logger.info("Dry run only. Add --apply to upload images.")
        return 0

    missing_settings = []
    if not settings.supabase_url:
        missing_settings.append("SUPABASE_URL")
    if settings.supabase_secret_key is None:
        missing_settings.append("SUPABASE_SECRET_KEY")
    if not settings.supabase_storage_bucket:
        missing_settings.append("SUPABASE_STORAGE_BUCKET")
    if missing_settings:
        logger.error("Missing Supabase Storage settings: %s", ", ".join(missing_settings))
        return 2

    checkpoint = None
    completed_paths: set[str] = set()
    if not args.no_resume:
        checkpoint_path = args.checkpoint or _default_checkpoint_path(
            settings.supabase_storage_bucket
        )
        checkpoint = StorageUploadCheckpoint(checkpoint_path)
        completed_paths = checkpoint.load()

    skipped = [image for image in selected if image.storage_path in completed_paths]
    pending = [image for image in selected if image.storage_path not in completed_paths]
    uploaded = 0
    already_exists = 0
    failed = 0
    aborted_early = False
    public_urls: dict[str, str] = {}

    timeout = httpx.Timeout(settings.supabase_storage_timeout_seconds)
    limits = httpx.Limits(
        max_connections=workers,
        max_keepalive_connections=workers,
    )
    with httpx.Client(timeout=timeout, limits=limits, follow_redirects=False) as client:
        uploader = SupabaseStorageUploader(
            supabase_url=settings.supabase_url,
            secret_key=settings.supabase_secret_key.get_secret_value(),
            bucket=settings.supabase_storage_bucket,
            bucket_public=bucket_public,
            max_file_bytes=settings.supabase_storage_max_standard_upload_bytes,
            client=client,
        )
        for image in skipped:
            public_url = uploader.public_url(image.storage_path)
            if public_url is not None:
                public_urls[image.storage_path] = public_url

        with ThreadPoolExecutor(max_workers=workers) as executor:
            for start in range(0, len(pending), workers):
                batch = pending[start : start + workers]
                future_images = {
                    executor.submit(uploader.upload, image, overwrite=args.overwrite): image
                    for image in batch
                }
                fatal_error = False
                for future in as_completed(future_images):
                    image = future_images[future]
                    try:
                        result = future.result()
                    except (StorageManifestError, StorageUploadError) as exc:
                        failed += 1
                        logger.error("%s", exc)
                        if isinstance(exc, StorageUploadError) and exc.fatal:
                            fatal_error = True
                        continue

                    if result.outcome == "uploaded":
                        uploaded += 1
                    else:
                        already_exists += 1
                    if checkpoint is not None:
                        checkpoint.append(result.storage_path)
                    if result.public_url is not None:
                        public_urls[result.storage_path] = result.public_url

                processed = min(start + len(batch), len(pending))
                if processed % 100 == 0 or processed == len(pending):
                    logger.info(
                        "Processed %d/%d pending images (uploaded=%d, existing=%d, failed=%d)",
                        processed,
                        len(pending),
                        uploaded,
                        already_exists,
                        failed,
                    )
                if fatal_error:
                    aborted_early = True
                    logger.error("Stopping early after a fatal Storage authorization/bucket error")
                    break

    public_urls_updated = 0
    if bucket_public and not args.no_update_csv:
        public_urls_updated = update_manifest_public_urls(manifest, public_urls)

    stats = UploadStats(
        selected=len(selected),
        pending=len(pending),
        uploaded=uploaded,
        already_exists=already_exists,
        skipped_checkpoint=len(skipped),
        failed=failed,
        public_urls_updated=public_urls_updated,
        aborted_early=aborted_early,
    )
    print(json.dumps(asdict(stats), ensure_ascii=False, indent=2))
    return 0 if failed == 0 and not aborted_early else 1


def _default_checkpoint_path(bucket: str) -> Path:
    safe_bucket = re.sub(r"[^A-Za-z0-9_.-]+", "_", bucket)
    return Path("artifacts") / "storage" / f"{safe_bucket}.checkpoint"


if __name__ == "__main__":
    raise SystemExit(main())

