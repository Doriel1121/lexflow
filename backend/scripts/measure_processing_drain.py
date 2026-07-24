"""Measure full document processing drain time.

This benchmark uploads real files without the test bypass, waits for the normal
Celery/OCR/AI pipeline to finish, then verifies OCR text, summary, metadata, and
optional semantic search readiness.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
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


TERMINAL_STATUSES = {"completed", "failed"}
DEFAULT_PROBE = "principles agreement"


@dataclass
class TargetUser:
    email: str
    user_id: int
    organization_id: int | None
    role: str


@dataclass
class FixtureFile:
    filename: str
    content: bytes
    content_type: str


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return ordered[index]


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


def make_generated_fixture(index: int, run_id: int) -> FixtureFile:
    content = f"""Processing drain test document {index}

Matter: Principles Agreement / הסכם עקרונות
Client: LexFlow Load Test Client {index}
Counterparty: Example Holdings Ltd.
Date: 2026-07-24
Amount: 125,000 ILS
Case number: LF-{run_id}-{index:04d}

This legal document describes a principles agreement, payment obligations,
delivery milestones, confidentiality duties, and a response deadline.
The purpose is to exercise text extraction, classification, metadata extraction,
summary generation, chunking, embeddings, and semantic search readiness.
"""
    return FixtureFile(
        filename=f"processing-drain-{run_id}-{index:04d}.txt",
        content=content.encode("utf-8"),
        content_type="text/plain",
    )


def load_fixture_files(sample_dir: Path | None, uploads: int, run_id: int) -> list[FixtureFile]:
    if not sample_dir:
        return [make_generated_fixture(i, run_id) for i in range(uploads)]

    if not sample_dir.exists() or not sample_dir.is_dir():
        raise RuntimeError(f"Sample directory not found: {sample_dir}")

    allowed_suffixes = {".pdf", ".docx", ".doc", ".txt", ".jpg", ".jpeg", ".png"}
    paths = [
        path
        for path in sorted(sample_dir.iterdir())
        if path.is_file() and path.suffix.lower() in allowed_suffixes
    ]
    if not paths:
        raise RuntimeError(f"No supported sample files found in: {sample_dir}")

    selected_count = len(paths) if uploads <= 0 else uploads

    fixtures: list[FixtureFile] = []
    for index in range(selected_count):
        source = paths[index % len(paths)]
        content_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        fixtures.append(
            FixtureFile(
                filename=f"processing-drain-{run_id}-{index:04d}-{source.name}",
                content=source.read_bytes(),
                content_type=content_type,
            )
        )
    return fixtures


async def fetch_metrics(client: httpx.AsyncClient) -> dict[str, Any] | None:
    try:
        response = await client.get("/metrics-lite", timeout=10)
        return response.json()
    except Exception:
        return None


async def upload_one(
    client: httpx.AsyncClient,
    token: str,
    fixture: FixtureFile,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = await client.post(
            "/v1/documents/",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (fixture.filename, fixture.content, fixture.content_type)},
            timeout=90,
        )
        duration_ms = (time.perf_counter() - started) * 1000
        body: dict[str, Any] = {}
        try:
            body = response.json()
        except Exception:
            pass
        return {
            "status": response.status_code,
            "duration_ms": duration_ms,
            "document_id": body.get("id"),
            "filename": fixture.filename,
            "error": body.get("detail") if response.status_code >= 400 else None,
        }
    except Exception as exc:
        return {
            "status": "error",
            "duration_ms": (time.perf_counter() - started) * 1000,
            "document_id": None,
            "filename": fixture.filename,
            "error": type(exc).__name__,
        }


async def fetch_status(client: httpx.AsyncClient, token: str, document_id: int) -> dict[str, Any]:
    response = await client.get(
        f"/v1/documents/{document_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


async def wait_for_processing(
    client: httpx.AsyncClient,
    token: str,
    document_ids: list[int],
    timeout_seconds: int,
    poll_seconds: float,
) -> tuple[dict[int, dict[str, Any]], dict[int, float]]:
    started = time.perf_counter()
    remaining = set(document_ids)
    final_statuses: dict[int, dict[str, Any]] = {}
    completed_after: dict[int, float] = {}

    while remaining and (time.perf_counter() - started) < timeout_seconds:
        for document_id in list(remaining):
            try:
                status_body = await fetch_status(client, token, document_id)
            except Exception as exc:
                status_body = {"status": "status_error", "stage": type(exc).__name__}

            status_value = str(status_body.get("status", "")).lower()
            final_statuses[document_id] = status_body
            if status_value in TERMINAL_STATUSES:
                remaining.remove(document_id)
                completed_after[document_id] = time.perf_counter() - started

        if remaining:
            await asyncio.sleep(poll_seconds)

    return final_statuses, completed_after


async def endpoint_ok(
    client: httpx.AsyncClient,
    token: str,
    document_id: int,
    suffix: str,
) -> bool:
    try:
        response = await client.get(
            f"/v1/documents/{document_id}/{suffix}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        return response.status_code == 200
    except Exception:
        return False


async def verify_outputs(
    client: httpx.AsyncClient,
    token: str,
    document_ids: list[int],
    concurrency: int,
) -> dict[str, Any]:
    semaphore = asyncio.Semaphore(concurrency)

    async def verify_one(document_id: int) -> dict[str, Any]:
        async with semaphore:
            text_ok, summary_ok, metadata_ok = await asyncio.gather(
                endpoint_ok(client, token, document_id, "text"),
                endpoint_ok(client, token, document_id, "summary"),
                endpoint_ok(client, token, document_id, "metadata"),
            )
            return {
                "document_id": document_id,
                "text": text_ok,
                "summary": summary_ok,
                "metadata": metadata_ok,
            }

    rows = await asyncio.gather(*(verify_one(document_id) for document_id in document_ids))
    return {
        "checked": len(rows),
        "text_ok": sum(1 for row in rows if row["text"]),
        "summary_ok": sum(1 for row in rows if row["summary"]),
        "metadata_ok": sum(1 for row in rows if row["metadata"]),
        "failed": [row for row in rows if not (row["text"] and row["summary"] and row["metadata"])],
    }


async def semantic_probe(
    client: httpx.AsyncClient,
    token: str,
    query: str,
    expected_ids: set[int],
) -> dict[str, Any]:
    if not query:
        return {"enabled": False}
    try:
        response = await client.get(
            "/v1/documents/semantic-search",
            params={"query": query, "limit": min(max(len(expected_ids), 5), 50)},
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        body = response.json()
        returned_ids = [row.get("id") for row in body if isinstance(row, dict)]
        return {
            "enabled": True,
            "status": response.status_code,
            "returned": len(returned_ids),
            "matched_uploaded": len(expected_ids.intersection(returned_ids)),
            "returned_ids": returned_ids[:20],
        }
    except Exception as exc:
        return {"enabled": True, "status": "error", "error": type(exc).__name__}


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


async def cleanup_documents(
    client: httpx.AsyncClient,
    token: str,
    document_ids: list[int],
    concurrency: int,
) -> dict[str, Any]:
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_delete(document_id: int) -> int | str:
        async with semaphore:
            return await delete_one(client, token, document_id)

    statuses = await asyncio.gather(*(bounded_delete(document_id) for document_id in document_ids))
    return {
        "attempted": len(statuses),
        "status_counts": {
            str(status): statuses.count(status)
            for status in sorted(set(statuses), key=str)
        },
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    run_id = int(time.time())
    target = await find_user()
    token = create_access_token(
        {
            "email": target.email,
            "user_id": target.user_id,
            "org_id": target.organization_id,
            "role": target.role,
        }
    )
    fixtures = load_fixture_files(
        Path(args.sample_dir) if args.sample_dir else None,
        args.uploads,
        run_id,
    )
    upload_count = len(fixtures)
    limits = httpx.Limits(
        max_connections=args.concurrency + 20,
        max_keepalive_connections=args.concurrency + 20,
    )

    async with httpx.AsyncClient(base_url=args.base_url, limits=limits) as client:
        before_metrics = await fetch_metrics(client)
        upload_semaphore = asyncio.Semaphore(args.concurrency)

        async def bounded_upload(fixture: FixtureFile) -> dict[str, Any]:
            async with upload_semaphore:
                return await upload_one(client, token, fixture)

        upload_started = time.perf_counter()
        upload_results = await asyncio.gather(*(bounded_upload(fixture) for fixture in fixtures))
        upload_wall_ms = (time.perf_counter() - upload_started) * 1000
        after_upload_metrics = await fetch_metrics(client)

        document_ids = [
            row["document_id"]
            for row in upload_results
            if isinstance(row.get("document_id"), int)
        ]

        drain_started = time.perf_counter()
        final_statuses, completed_after = await wait_for_processing(
            client,
            token,
            document_ids,
            args.timeout_seconds,
            args.poll_seconds,
        )
        drain_wall_ms = (time.perf_counter() - drain_started) * 1000
        after_drain_metrics = await fetch_metrics(client)

        completed_ids = [
            document_id
            for document_id in document_ids
            if str(final_statuses.get(document_id, {}).get("status", "")).lower() == "completed"
        ]
        verification = await verify_outputs(
            client,
            token,
            completed_ids,
            min(args.concurrency, 25),
        )
        semantic = await semantic_probe(client, token, args.semantic_query, set(completed_ids))
        cleanup = (
            await cleanup_documents(client, token, document_ids, min(args.concurrency, 25))
            if args.cleanup
            else {"attempted": 0, "status_counts": {}}
        )
        after_cleanup_metrics = await fetch_metrics(client)

    upload_durations = [float(row["duration_ms"]) for row in upload_results]
    terminal_times = list(completed_after.values())
    status_counts: dict[str, int] = {}
    for document_id in document_ids:
        status_value = str(final_statuses.get(document_id, {}).get("status", "missing")).lower()
        status_counts[status_value] = status_counts.get(status_value, 0) + 1

    return {
        "target_user": {
            "user_id": target.user_id,
            "organization_id": target.organization_id,
        },
        "config": {
            "uploads": upload_count,
            "concurrency": args.concurrency,
            "sample_dir": args.sample_dir,
            "timeout_seconds": args.timeout_seconds,
            "poll_seconds": args.poll_seconds,
            "cleanup": args.cleanup,
            "semantic_query": args.semantic_query,
        },
        "upload": {
            "status_counts": {
                str(status): [str(row["status"]) for row in upload_results].count(str(status))
                for status in sorted({str(row["status"]) for row in upload_results})
            },
            "created_documents": len(document_ids),
            "wall_ms": round(upload_wall_ms, 1),
            "throughput_uploads_per_sec": round(upload_count / (upload_wall_ms / 1000), 2)
            if upload_wall_ms
            else 0,
            "ms_avg": round(statistics.mean(upload_durations), 1) if upload_durations else 0,
            "ms_p95": round(percentile(upload_durations, 95), 1),
            "errors": [row for row in upload_results if row.get("status") != 201][:20],
        },
        "drain": {
            "status_counts": status_counts,
            "wall_ms": round(drain_wall_ms, 1),
            "completed": len(completed_ids),
            "failed": status_counts.get("failed", 0),
            "timed_out": len(document_ids) - len(completed_after),
            "seconds_avg": round(statistics.mean(terminal_times), 2) if terminal_times else 0,
            "seconds_p50": round(percentile(terminal_times, 50), 2),
            "seconds_p95": round(percentile(terminal_times, 95), 2),
            "seconds_max": round(max(terminal_times), 2) if terminal_times else 0,
            "unfinished_sample": [
                {"document_id": document_id, **final_statuses.get(document_id, {})}
                for document_id in document_ids
                if document_id not in completed_after
            ][:20],
        },
        "verification": verification,
        "semantic_probe": semantic,
        "cleanup": cleanup,
        "metrics": {
            "before": before_metrics,
            "after_upload": after_upload_metrics,
            "after_drain": after_drain_metrics,
            "after_cleanup": after_cleanup_metrics,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--uploads", type=int, default=10, help="Number of uploads. Use 0 with --sample-dir to upload every supported file once.")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--sample-dir", default="")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--semantic-query", default=DEFAULT_PROBE)
    parser.add_argument("--cleanup", action=argparse.BooleanOptionalAction, default=False)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
