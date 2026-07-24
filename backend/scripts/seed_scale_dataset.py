"""Seed synthetic scale data for performance testing without calling OCR/AI.

Example inside backend container:
    python scripts/seed_scale_dataset.py --users 1000 --documents 20000 --batch-size 1000

The script creates one synthetic organization by default, test users, and READY
PDF-like document rows with optional lightweight chunks. It is intended for local
or staging performance tests only.
"""
from __future__ import annotations

import argparse
import asyncio
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, select

from app.db.models.document import Document, DocumentChunk, DocumentProcessingStatus
from app.db.models.organization import Organization
from app.db.models.user import User, UserRole
from app.db.session import AsyncSessionLocal

SYNTHETIC_PREFIX = "scale-test"
SYNTHETIC_PASSWORD_HASH = "$2b$12$scaleSyntheticHashForLoadTestingOnly"


def document_content(index: int) -> str:
    terms = ["הסכם עקרונות", "תמל 2044", "נספח", "בקשה", "התחדשות עירונית"]
    term = terms[index % len(terms)]
    return f"{term} synthetic legal document {index}. " * 20


async def ensure_org(slug: str) -> Organization:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Organization).where(Organization.slug == slug))
        org = result.scalar_one_or_none()
        if org:
            return org
        org = Organization(name="Scale Test Organization", slug=slug, is_active=True)
        db.add(org)
        await db.commit()
        await db.refresh(org)
        return org


async def cleanup(slug: str) -> None:
    async with AsyncSessionLocal() as db:
        org_id = await db.scalar(select(Organization.id).where(Organization.slug == slug))
        if not org_id:
            print(f"No synthetic organization found for slug={slug}")
            return
        doc_ids = await db.scalars(select(Document.id).where(Document.organization_id == org_id))
        ids = list(doc_ids.all())
        if ids:
            await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(ids)))
            await db.execute(delete(Document).where(Document.id.in_(ids)))
        await db.execute(delete(User).where(User.organization_id == org_id))
        await db.execute(delete(Organization).where(Organization.id == org_id))
        await db.commit()
        print(f"Deleted synthetic org={slug}, users/docs/chunks")


async def seed(users: int, documents: int, chunks_per_document: int, batch_size: int, slug: str) -> None:
    org = await ensure_org(slug)
    created_users = 0
    created_docs = 0
    created_chunks = 0

    async with AsyncSessionLocal() as db:
        existing_users = await db.scalar(
            select(func.count(User.id)).where(User.organization_id == org.id, User.email.like(f"{SYNTHETIC_PREFIX}-%"))
        ) or 0
        existing_docs = await db.scalar(
            select(func.count(Document.id)).where(Document.organization_id == org.id, Document.filename.like(f"{SYNTHETIC_PREFIX}-%"))
        ) or 0

    for start in range(existing_users, users, batch_size):
        end = min(start + batch_size, users)
        async with AsyncSessionLocal() as db:
            db.add_all([
                User(
                    email=f"{SYNTHETIC_PREFIX}-{i}@example.test",
                    hashed_password=SYNTHETIC_PASSWORD_HASH,
                    full_name=f"Scale User {i}",
                    organization_id=org.id,
                    role=UserRole.LAWYER,
                    is_active=True,
                )
                for i in range(start, end)
            ])
            await db.commit()
        created_users += end - start
        print(f"users: {end}/{users}")

    async with AsyncSessionLocal() as db:
        user_ids = list((await db.scalars(select(User.id).where(User.organization_id == org.id))).all())
    if not user_ids:
        raise RuntimeError("No users available for document ownership")

    for start in range(existing_docs, documents, batch_size):
        end = min(start + batch_size, documents)
        async with AsyncSessionLocal() as db:
            docs: list[Document] = []
            now = datetime.utcnow()
            for i in range(start, end):
                doc = Document(
                    filename=f"{SYNTHETIC_PREFIX}-{i:06d}-הסכם.pdf",
                    s3_url=f"http://localhost:8000/uploads/synthetic/{i:06d}.pdf",
                    content=document_content(i),
                    classification="synthetic_contract" if i % 2 == 0 else "synthetic_motion",
                    language="he" if i % 3 else "en",
                    page_count=(i % 120) + 1,
                    processing_status=DocumentProcessingStatus.COMPLETED,
                    processing_stage="completed",
                    processing_progress=100.0,
                    uploaded_by_user_id=user_ids[i % len(user_ids)],
                    organization_id=org.id,
                    created_at=now - timedelta(minutes=i),
                    updated_at=now - timedelta(minutes=i),
                    processed_chunks=chunks_per_document,
                    total_chunks=chunks_per_document,
                    ai_health={"synthetic": True},
                )
                docs.append(doc)
                db.add(doc)
            await db.flush()

            if chunks_per_document > 0:
                chunks = []
                for doc in docs:
                    for chunk_index in range(chunks_per_document):
                        chunks.append(
                            DocumentChunk(
                                document_id=doc.id,
                                chunk_index=chunk_index,
                                page_start=chunk_index + 1,
                                page_end=chunk_index + 1,
                                text_content=f"{document_content(doc.id)} chunk {chunk_index}",
                            )
                        )
                db.add_all(chunks)
                created_chunks += len(chunks)
            await db.commit()
        created_docs += end - start
        print(f"documents: {end}/{documents}")

    print(
        f"Seed complete org={org.slug} users_created={created_users} "
        f"documents_created={created_docs} chunks_created={created_chunks}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=1000)
    parser.add_argument("--documents", type=int, default=20000)
    parser.add_argument("--chunks-per-document", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--org-slug", default="scale-test-org")
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()

    if args.cleanup:
        asyncio.run(cleanup(args.org_slug))
        return

    if args.users <= 0 or args.documents <= 0 or args.batch_size <= 0:
        raise SystemExit("users, documents, and batch-size must be positive")
    if args.documents > 100000 and not args.org_slug.startswith(SYNTHETIC_PREFIX):
        raise SystemExit("Refusing very large seed without synthetic org slug")

    asyncio.run(seed(args.users, args.documents, args.chunks_per_document, args.batch_size, args.org_slug))


if __name__ == "__main__":
    main()