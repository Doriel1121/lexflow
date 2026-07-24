"""Remove orphaned objects created by the upload load-test script.

Defaults to a narrow, test-only prefix and requires --confirm to delete.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.storage import storage_service


DEFAULT_PREFIX = "inbox/unprocessed/upload-load-"


async def cleanup_object_storage(prefix: str, confirm: bool) -> tuple[int, int]:
    bucket_name = getattr(storage_service, "bucket_name", None)
    s3_client = getattr(storage_service, "s3_client", None)
    if not bucket_name or not s3_client:
        return 0, 0

    paginator = s3_client.get_paginator("list_objects_v2")
    pages = await asyncio.to_thread(
        lambda: list(paginator.paginate(Bucket=bucket_name, Prefix=prefix))
    )
    keys = [
        item["Key"]
        for page in pages
        for item in page.get("Contents", [])
        if item.get("Key")
    ]

    if not confirm or not keys:
        return len(keys), 0

    deleted = 0
    for offset in range(0, len(keys), 1000):
        batch = keys[offset : offset + 1000]
        response = await asyncio.to_thread(
            s3_client.delete_objects,
            Bucket=bucket_name,
            Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
        )
        deleted += len(batch) - len(response.get("Errors", []))
    return len(keys), deleted


async def cleanup_local_storage(prefix: str, confirm: bool) -> tuple[int, int]:
    upload_dir = getattr(storage_service, "upload_dir", None)
    if not upload_dir:
        return 0, 0

    root = Path(upload_dir).resolve()
    files = [path for path in root.rglob("*") if path.is_file() and path.as_posix().find(prefix) >= 0]
    if not confirm or not files:
        return len(files), 0

    deleted = 0
    for path in files:
        path.unlink()
        deleted += 1
    return len(files), deleted


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    object_found, object_deleted = await cleanup_object_storage(args.prefix, args.confirm)
    local_found, local_deleted = await cleanup_local_storage(args.prefix, args.confirm)

    mode = "deleted" if args.confirm else "dry_run"
    print(
        {
            "mode": mode,
            "prefix": args.prefix,
            "object_storage_found": object_found,
            "object_storage_deleted": object_deleted,
            "local_storage_found": local_found,
            "local_storage_deleted": local_deleted,
        }
    )


if __name__ == "__main__":
    asyncio.run(main())
