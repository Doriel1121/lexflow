from pathlib import Path

lines = Path("app/workers/document_tasks.py").read_text(encoding="utf-8").splitlines()
start = next(i for i, l in enumerate(lines) if l.strip() == "start_time = time.time()")
end = next(
    i
    for i in range(start, len(lines))
    if lines[i].strip() == "try:" and i + 1 < len(lines) and "run_async(_run())" in lines[i + 1]
)
body = lines[start:end]
dedented = [l[4:] if l.startswith("        ") else l for l in body]
header = '''"""Unified document processing pipeline (Celery + BackgroundTasks)."""
from __future__ import annotations

import asyncio
import logging
import time
import traceback as tb
from typing import Callable, Optional

import dateparser
from sqlalchemy import delete, select, update

from app.core.config import settings
from app.crud.document import document_crud
from app.db.models.deadline import Deadline, DeadlineType
from app.db.models.document import Document, DocumentChunk, DocumentProcessingStatus
from app.db.models.document_processing_log import DocumentProcessingLog
from app.db.models.document_metadata import DocumentMetadata
from app.db.models.summary import Summary
from app.db.models.organization import Organization
from app.services.ai.ner_service import ner_service
from app.services.ai_utils import valid_embedding
from app.services.collections_analysis import classification_from_analysis
from app.services.document_chunker import document_chunker
from app.services.document_intelligence import document_intelligence_service
from app.services.document_notifications import create_org_notification
from app.services.llm import llm_service
from app.services.ocr import ocr_service
from app.services.text_normalization import text_normalization_service

logger = logging.getLogger(__name__)


def _set_ai_health(doc: Document, **fields) -> None:
    health = dict(doc.ai_health or {})
    health.update(fields)
    doc.ai_health = health


async def run_document_pipeline(
    document_id: int,
    file_path: str,
    user_id: int,
    organization_id: int,
    *,
    session_factory,
    allow_embed_fanout: bool = True,
    queue_embed_batch: Optional[Callable[[int, list[int]], None]] = None,
) -> None:
'''
text = header + "\n".join(dedented)
text = text.replace("_create_org_notification", "create_org_notification")
text = text.replace("CeleryAsyncSessionLocal", "session_factory")
Path("app/services/document_pipeline.py").write_text(text, encoding="utf-8")
print("lines", len(text.splitlines()))
