"""Measure key document endpoint latency and payload sizes against a running API.

Usage inside backend container:
    python scripts/measure_document_endpoints.py --runs 20

The script creates a short-lived JWT for the first user/document pair in the DB,
then measures the lightweight detail endpoint and on-demand tab endpoints.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models.document import Document
from app.db.models.organization import Organization
from app.db.models.user import User
from app.db.session import AsyncSessionLocal


@dataclass
class Target:
    user_id: int
    email: str
    organization_id: int | None
    document_id: int


async def find_target(org_slug: str | None = None) -> Target:
    async with AsyncSessionLocal() as db:
        query = (
            select(User, Document)
            .join(Document, Document.organization_id == User.organization_id)
        )
        if org_slug:
            query = query.join(Organization, Organization.id == Document.organization_id).where(
                Organization.slug == org_slug
            )
        result = await db.execute(
            query.order_by(Document.page_count.desc().nullslast(), Document.id.desc()).limit(1)
        )
        row = result.first()
        if not row:
            raise RuntimeError("No user/document pair found for measurement")
        user, document = row
        return Target(
            user_id=user.id,
            email=user.email,
            organization_id=user.organization_id,
            document_id=document.id,
        )


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return ordered[index]


def fetch(url: str, token: str) -> tuple[int, int, float]:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        body = error.read()
        status = error.code
    duration_ms = (time.perf_counter() - started) * 1000
    return status, len(body), duration_ms


def summarize(samples: list[tuple[int, int, float]]) -> dict[str, Any]:
    statuses = [status for status, _size, _duration in samples]
    sizes = [size for _status, size, _duration in samples]
    durations = [duration for _status, _size, duration in samples]
    return {
        "status_counts": {str(status): statuses.count(status) for status in sorted(set(statuses))},
        "bytes_avg": round(statistics.mean(sizes), 1),
        "ms_avg": round(statistics.mean(durations), 1),
        "ms_p50": round(percentile(durations, 50), 1),
        "ms_p95": round(percentile(durations, 95), 1),
        "ms_max": round(max(durations), 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--org-slug", default=None)
    args = parser.parse_args()

    target = asyncio.run(find_target(args.org_slug))
    token = create_access_token(
        {
            "email": target.email,
            "user_id": target.user_id,
            "org_id": target.organization_id,
            "role": "admin",
        }
    )

    endpoints = {
        "list": "/v1/documents?skip=0&limit=50",
        "detail": f"/v1/documents/{target.document_id}",
        "summary": f"/v1/documents/{target.document_id}/summary",
        "metadata": f"/v1/documents/{target.document_id}/metadata",
        "ocr_text": f"/v1/documents/{target.document_id}/text",
    }

    results: dict[str, Any] = {
        "target": {
            "document_id": target.document_id,
            "organization_id": target.organization_id,
        },
        "runs": args.runs,
        "endpoints": {},
    }

    # Warmup: trigger imports/pools outside measured loop.
    for path in endpoints.values():
        fetch(args.base_url + path, token)

    for name, path in endpoints.items():
        samples = [fetch(args.base_url + path, token) for _ in range(args.runs)]
        results["endpoints"][name] = summarize(samples)

    detail_size = results["endpoints"]["detail"]["bytes_avg"]
    text_size = results["endpoints"]["ocr_text"]["bytes_avg"]
    if detail_size and text_size:
        results["payload_comparison"] = {
            "ocr_text_bytes_vs_detail_bytes": round(text_size / detail_size, 1),
            "estimated_old_detail_bytes_if_ocr_inline": round(detail_size + text_size, 1),
            "estimated_detail_reduction_percent_without_inline_ocr": round(
                (text_size / (detail_size + text_size)) * 100,
                1,
            ),
        }

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()