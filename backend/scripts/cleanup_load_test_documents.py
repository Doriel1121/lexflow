"""Delete load-test document records and physical files.

Defaults to a dry run. Pass --confirm to delete documents whose filenames match
known benchmark prefixes.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import or_, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.models.document import Document
from app.db.session import AsyncSessionLocal
from app.services.storage import storage_service


DEFAULT_PREFIXES = ("processing-drain-", "upload-load-")


async def cleanup_documents(prefixes: tuple[str, ...], confirm: bool) -> dict[str, object]:
    async with AsyncSessionLocal() as db:
        filters = [Document.filename.like(f"{prefix}%") for prefix in prefixes]
        result = await db.execute(
            select(Document.id, Document.filename, Document.s3_url)
            .where(or_(*filters))
            .order_by(Document.id)
        )
        rows = result.all()

        deleted_files = 0
        failed_files: list[dict[str, object]] = []

        if confirm:
            for document_id, filename, s3_url in rows:
                if s3_url:
                    deleted = await storage_service.delete_file_by_url(s3_url)
                    if deleted:
                        deleted_files += 1
                    else:
                        failed_files.append(
                            {
                                "document_id": document_id,
                                "filename": filename,
                                "s3_url": s3_url,
                            }
                        )

                document = await db.get(Document, document_id)
                if document:
                    await db.delete(document)

            await db.commit()

        return {
            "mode": "deleted" if confirm else "dry_run",
            "prefixes": prefixes,
            "matched_documents": len(rows),
            "deleted_documents": len(rows) if confirm else 0,
            "deleted_files": deleted_files,
            "file_delete_misses": len(failed_files),
            "file_delete_miss_sample": failed_files[:20],
            "document_sample": [
                {"id": document_id, "filename": filename}
                for document_id, filename, _ in rows[:20]
            ],
        }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--prefix", action="append", dest="prefixes")
    args = parser.parse_args()

    prefixes = tuple(args.prefixes or DEFAULT_PREFIXES)
    print(await cleanup_documents(prefixes, args.confirm))


if __name__ == "__main__":
    asyncio.run(main())
