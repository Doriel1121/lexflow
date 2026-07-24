"""Measure concurrent document upload acceptance and cleanup test files.

Safe local/staging default uses X-LexFlow-Test-Skip-Processing so uploads do not
trigger OCR/AI. The API only honors this when ENABLE_TEST_UPLOAD_BYPASS=true.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import create_access_token
from app.db.models.user import User
from app.db.session import AsyncSessionLocal


@dataclass
class TargetUser:
    email: str
    user_id: int
    organization_id: int | None
    role: str


async def find_user() -> TargetUser:
    async with AsyncSessionLocal() as db:
        user = (await db.scalars(select(User).where(User.is_active == True).limit(1))).first()  # noqa: E712
        if not user:
            raise RuntimeError("No active user found")
        return TargetUser(
            email=user.email,
            user_id=user.id,
            organization_id=user.organization_id,
            role=user.role.value if hasattr(user.role, "value") else str(user.role),
        )


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return ordered[index]


async def fetch_metrics(client: httpx.AsyncClient) -> dict[str, Any] | None:
    try:
        response = await client.get("/metrics-lite", timeout=10)
        return response.json()
    except Exception:
        return None


async def upload_one(
    client: httpx.AsyncClient,
    token: str,
    index: int,
    content: bytes,
    skip_processing: bool,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    if skip_processing:
        headers["X-LexFlow-Test-Skip-Processing"] = "true"
    started = time.perf_counter()
    filename = f"upload-load-{int(time.time())}-{index:05d}.pdf"
    try:
        response = await client.post(
            "/v1/documents/",
            headers=headers,
            files={"file": (filename, content, "application/pdf")},
            timeout=60,
        )
        duration_ms = (time.perf_counter() - started) * 1000
        document_id = None
        try:
            body = response.json()
            document_id = body.get("id")
        except Exception:
            pass
        return {
            "status": response.status_code,
            "duration_ms": duration_ms,
            "bytes": len(response.content),
            "document_id": document_id,
        }
    except Exception as exc:
        return {
            "status": "error",
            "duration_ms": (time.perf_counter() - started) * 1000,
            "bytes": 0,
            "error": type(exc).__name__,
            "document_id": None,
        }


async def delete_one(client: httpx.AsyncClient, token: str, document_id: int) -> int | str:
    try:
        response = await client.delete(
            f"/v1/documents/{document_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        return response.status_code
    except Exception as exc:
        return type(exc).__name__

async def run(args: argparse.Namespace) -> dict[str, Any]:
    target = await find_user()
    token = create_access_token(
        {
            "email": target.email,
            "user_id": target.user_id,
            "org_id": target.organization_id,
            "role": target.role,
        }
    )
    content = b"%PDF-1.4\n% upload load test\n" + (b"x" * max(args.file_bytes - 28, 0))
    limits = httpx.Limits(
        max_connections=args.concurrency + 10,
        max_keepalive_connections=args.concurrency + 10,
    )
    async with httpx.AsyncClient(base_url=args.base_url, limits=limits) as client:
        before_metrics = await fetch_metrics(client)
        semaphore = asyncio.Semaphore(args.concurrency)

        async def bounded_upload(index: int) -> dict[str, Any]:
            async with semaphore:
                return await upload_one(client, token, index, content, args.skip_processing)

        started = time.perf_counter()
        results = await asyncio.gather(*(bounded_upload(i) for i in range(args.uploads)))
        wall_ms = (time.perf_counter() - started) * 1000
        after_metrics = await fetch_metrics(client)

        document_ids = [r["document_id"] for r in results if isinstance(r.get("document_id"), int)]
        cleanup_statuses: list[int | str] = []
        if args.cleanup and document_ids:
            cleanup_semaphore = asyncio.Semaphore(min(args.concurrency, 50))

            async def bounded_delete(document_id: int) -> int | str:
                async with cleanup_semaphore:
                    return await delete_one(client, token, document_id)

            cleanup_statuses = await asyncio.gather(*(bounded_delete(doc_id) for doc_id in document_ids))
        final_metrics = await fetch_metrics(client)

    statuses = [str(r["status"]) for r in results]
    durations = [float(r["duration_ms"]) for r in results]
    return {
        "target_user": {
            "user_id": target.user_id,
            "organization_id": target.organization_id,
        },
        "config": {
            "uploads": args.uploads,
            "concurrency": args.concurrency,
            "file_bytes": len(content),
            "skip_processing": args.skip_processing,
            "cleanup": args.cleanup,
        },
        "summary": {
            "status_counts": {status: statuses.count(status) for status in sorted(set(statuses))},
            "created_documents": len(document_ids),
            "wall_ms": round(wall_ms, 1),
            "throughput_uploads_per_sec": round(args.uploads / (wall_ms / 1000), 2) if wall_ms else 0,
            "ms_avg": round(statistics.mean(durations), 1) if durations else 0,
            "ms_p50": round(percentile(durations, 50), 1),
            "ms_p95": round(percentile(durations, 95), 1),
            "ms_max": round(max(durations), 1) if durations else 0,
        },
        "cleanup": {
            "attempted": len(cleanup_statuses),
            "status_counts": {
                str(status): cleanup_statuses.count(status)
                for status in sorted(set(cleanup_statuses), key=str)
            } if cleanup_statuses else {},
        },
        "metrics": {
            "before": before_metrics,
            "after_upload": after_metrics,
            "after_cleanup": final_metrics,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--uploads", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=25)
    parser.add_argument("--file-bytes", type=int, default=4096)
    parser.add_argument("--skip-processing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--cleanup", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()