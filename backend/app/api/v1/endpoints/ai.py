import json
import logging
import asyncio
import hashlib
import re
import time
import uuid
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.api import deps
from app.db.models.document import Document, DocumentChunk
from app.db.models.document_metadata import DocumentMetadata
from app.db.models.case import Case
from app.db.models.summary import Summary
from app.db.models.user import User as DBUser, UserRole
from app.schemas.ai import AskAIRequest, AskAIResponse, Citation
from app.services.ai_quota import AIQuotaExceeded
from app.services.ask_ai_prompting import (
    AskAIIntent,
    build_ask_ai_json_prompt,
    build_ask_ai_prompt,
    build_document_brief,
    detect_ask_ai_intent,
    render_ask_ai_answer,
)
from app.services.llm import llm_service
from app.core.ai_router import AIIntent, AIRiskLevel
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Basic Redis setup for caching
redis_client = (
    Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    if hasattr(settings, "REDIS_URL")
    else None
)
CACHE_TTL = 3600  # 1 hour
CACHE_TIMEOUT_SECONDS = 2.0


def _routing_for_ask_ai_intent(intent: AskAIIntent) -> tuple[AIIntent, AIRiskLevel, bool]:
    if intent in {
        AskAIIntent.LEGAL_ANALYSIS,
        AskAIIntent.RISK_ANALYSIS,
        AskAIIntent.NEXT_STEPS,
        AskAIIntent.DRAFTING_REQUEST,
    }:
        return AIIntent.LEGAL_REASONING, AIRiskLevel.HIGH, True
    if intent == AskAIIntent.DEADLINES_OBLIGATIONS:
        return AIIntent.DOCUMENT_ANALYSIS, AIRiskLevel.HIGH, True
    if intent == AskAIIntent.SUMMARY:
        return AIIntent.SUMMARIZATION, AIRiskLevel.LOW, False
    return AIIntent.DOCUMENT_QA, AIRiskLevel.MEDIUM, False

HEBREW_STOPWORDS = {
    "איזה", "איזו", "אילו", "מה", "מי", "האם", "איך", "כיצד", "למה", "מדוע", "מתי",
    "היכן", "איפה", "כמה", "של", "את", "על", "עם", "אל", "מ", "ב", "ל", "ה", "ו",
    "זה", "זו", "אלו", "אלה", "הוא", "היא", "הם", "הן", "הזה", "הזאת", "כל", "או", "גם"
}

def _extract_query_keywords(question: str) -> List[str]:
    raw_words = [re.sub(r'[^\wא-ת]+', '', w) for w in question.split()]
    words = [w for w in raw_words if len(w) >= 2 and w not in HEBREW_STOPWORDS]
    expanded = set(words)
    for w in words:
        if w in ('תוכנית', 'תכנית'):
            expanded.update(['תוכנית', 'תכנית', 'תמל'])
        elif w in ('מספר', 'מס'):
            expanded.update(['מספר', 'מס'])
    return list(expanded)


def _is_broad_document_question(intent: AskAIIntent, question: str) -> bool:
    normalized = (question or '').lower()
    broad_markers = (
        'analyze', 'analysis', 'summarize', 'summary', 'overview', 'what is this document',
        'main points', 'key points', 'risk', 'risks', 'obligations', 'deadlines',
        '\u05e0\u05ea\u05d7', '\u05e0\u05d9\u05ea\u05d5\u05d7', '\u05e1\u05db\u05dd', '\u05ea\u05e1\u05db\u05dd', '\u05e1\u05d9\u05db\u05d5\u05dd', '\u05ea\u05e7\u05e6\u05d9\u05e8', '\u05e2\u05d9\u05e7\u05e8\u05d9', '\u05de\u05d4 \u05d4\u05de\u05e1\u05de\u05da',
        '\u05e1\u05d9\u05db\u05d5\u05e0\u05d9\u05dd', '\u05d7\u05d5\u05d1\u05d5\u05ea', '\u05d4\u05ea\u05d7\u05d9\u05d9\u05d1\u05d5\u05d9\u05d5\u05ea', '\u05de\u05d5\u05e2\u05d3\u05d9\u05dd', '\u05d3\u05d3\u05dc\u05d9\u05d9\u05e0\u05d9\u05dd',
    )
    return intent in {
        AskAIIntent.SUMMARY,
        AskAIIntent.LEGAL_ANALYSIS,
        AskAIIntent.RISK_ANALYSIS,
        AskAIIntent.DEADLINES_OBLIGATIONS,
    } or any(marker in normalized for marker in broad_markers)


async def get_cache(key: str) -> Optional[Dict[str, Any]]:
    if not redis_client:
        return None
    try:
        cached = await asyncio.wait_for(redis_client.get(key), timeout=CACHE_TIMEOUT_SECONDS)
        if cached:
            return json.loads(cached)
    except asyncio.TimeoutError:
        logger.warning("Ask AI cache get timed out; continuing without cache.")
    except Exception as e:
        logger.warning(f"Cache get error: {e}")
    return None

async def set_cache(key: str, value: Dict[str, Any]):
    if not redis_client:
        return
    try:
        await asyncio.wait_for(
            redis_client.setex(key, CACHE_TTL, json.dumps(value)),
            timeout=CACHE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("Ask AI cache set timed out; response returned without cache write.")
    except Exception as e:
        logger.warning(f"Cache set error: {e}")

def generate_cache_key(request: AskAIRequest, org_id: Optional[int]) -> str:
    # Stable hash of request parameters (versioned v6 for grounded selected-document prompting)
    req_data = f"v6:{request.question}:{request.case_id}:{request.document_ids}:{request.top_k}:{org_id}"
    return f"rag:query:{hashlib.md5(req_data.encode()).hexdigest()}"


def _quota_http_exception(exc: AIQuotaExceeded) -> HTTPException:
    status_info = exc.status
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "code": "ai_quota_exceeded",
            "limit_name": status_info.limit_name,
            "used": status_info.used,
            "limit": status_info.limit,
            "reset_at": status_info.reset_at.isoformat(),
        },
    )

def _is_hebrew(text: str) -> bool:
    for ch in text:
        if "\u0590" <= ch <= "\u05FF":
            return True
    return False

async def _load_document_brief(
    db: AsyncSession,
    document_ids: List[int],
    case_obj: Optional[Case],
) -> str:
    if not document_ids and not case_obj:
        return ""

    sections: List[str] = []
    if case_obj:
        sections.append(f"Case: {case_obj.title}")
        if case_obj.description:
            sections.append(f"Case description: {case_obj.description}")
        sections.append("")

    if not document_ids:
        return "\n".join(sections).strip()

    docs_res = await db.execute(select(Document).where(Document.id.in_(document_ids)))
    documents = {doc.id: doc for doc in docs_res.scalars().all()}

    summaries_res = await db.execute(select(Summary).where(Summary.document_id.in_(document_ids)))
    summaries = {summary.document_id: summary for summary in summaries_res.scalars().all()}

    metadata_res = await db.execute(
        select(DocumentMetadata).where(DocumentMetadata.document_id.in_(document_ids))
    )
    metadata_by_doc = {metadata.document_id: metadata for metadata in metadata_res.scalars().all()}

    items: List[Dict[str, Any]] = []
    for doc_id in document_ids:
        doc = documents.get(doc_id)
        if not doc:
            continue
        summary = summaries.get(doc_id)
        metadata = metadata_by_doc.get(doc_id)
        items.append({
            "id": doc.id,
            "filename": doc.filename,
            "classification": doc.classification,
            "language": doc.language,
            "page_count": doc.page_count,
            "summary": summary.content if summary else None,
            "parties": summary.parties if summary else None,
            "key_dates": summary.key_dates if summary else None,
            "missing_documents_suggestion": summary.missing_documents_suggestion if summary else None,
            "dates": metadata.dates if metadata else None,
            "entities": metadata.entities if metadata else None,
            "amounts": metadata.amounts if metadata else None,
            "case_numbers": metadata.case_numbers if metadata else None,
            "keywords": metadata.extracted_keywords if metadata else None,
        })

    document_brief = build_document_brief(items)
    if document_brief:
        sections.append(document_brief)
    return "\n".join(sections).strip()

@router.post("/ask", response_model=AskAIResponse)
async def ask_ai(
    request: AskAIRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: DBUser = Depends(deps.get_current_active_user),
    org_id: Optional[int] = Depends(deps.get_current_org),
):
    """
    Retrieval-Augmented Generation (RAG) endpoint.
    Ask questions about documents or a specific case.
    """
    request_id = uuid.uuid4().hex[:8]
    started_at = time.perf_counter()
    logger.info(
        "AskAI[%s] start user=%s org=%s case=%s docs=%s top_k=%s question_chars=%s",
        request_id,
        current_user.id,
        org_id,
        request.case_id,
        len(request.document_ids or []),
        request.top_k,
        len(request.question or ""),
    )

    # 1. Security & Validation
    cache_key = generate_cache_key(request, org_id)
    cached_res = await get_cache(cache_key)
    if cached_res:
        logger.info("AskAI[%s] cache hit elapsed_ms=%.1f", request_id, (time.perf_counter() - started_at) * 1000)
        return AskAIResponse(**cached_res)

    # Validate Case Access if provided
    case_obj = None
    if request.case_id:
        case_obj = await db.get(Case, request.case_id)
        if not case_obj:
            raise HTTPException(status_code=404, detail="Case not found")
        deps.verify_resource_access(case_obj, current_user)

    # 2. Semantic Retrieval
    # Generate embedding for the question
    from app.services.ai_utils import valid_embedding

    timeout_seconds = max(10.0, float(settings.ASK_AI_TIMEOUT_SECONDS or 45))
    try:
        question_vector = await asyncio.wait_for(
            llm_service.generate_embedding(
                request.question,
                db=db,
                organization_id=org_id,
                task_type="embedding.rag_query",
            ),
            timeout=min(timeout_seconds, 15.0),
        )
    except asyncio.TimeoutError:
        logger.warning("AskAI[%s] timed out elapsed_ms=%.1f", request_id, (time.perf_counter() - started_at) * 1000)
        raise HTTPException(
            status_code=504,
            detail="AI Q&A timed out while preparing the question. Please try again.",
        )
    except AIQuotaExceeded as exc:
        raise _quota_http_exception(exc)
    if not valid_embedding(question_vector):
        raise HTTPException(
            status_code=503,
            detail="AI Q&A is temporarily unavailable (embedding service failed).",
        )

    intent = detect_ask_ai_intent(request.question)
    is_broad_document_question = _is_broad_document_question(intent, request.question)

    # Construct candidate query with pgvector cosine distance
    # We join with Document to ensure org/user isolation
    stmt = (
        select(
            DocumentChunk.text_content,
            DocumentChunk.document_id,
            DocumentChunk.page_number,
            DocumentChunk.chunk_index,
            DocumentChunk.embedding.cosine_distance(question_vector).label("distance")
        )
        .join(Document, Document.id == DocumentChunk.document_id)
    )

    # Security: Organization Isolation
    if org_id is not None:
        stmt = stmt.where(Document.organization_id == org_id)
    else:
        # Independent user: only their own documents
        stmt = stmt.where(Document.uploaded_by_user_id == current_user.id)

    # Filters: Case or Document IDs
    if request.case_id:
        stmt = stmt.where(Document.case_id == request.case_id)
    
    if request.document_ids:
        stmt = stmt.where(Document.id.in_(request.document_ids))

    # Fetch a candidate pool for hybrid ranking
    stmt = stmt.order_by("distance").limit(max(request.top_k * 18, 150))
    
    retrieval_started_at = time.perf_counter()
    result = await db.execute(stmt)
    candidate_rows = result.all()
    logger.info(
        "AskAI[%s] vector retrieval rows=%s elapsed_ms=%.1f",
        request_id,
        len(candidate_rows),
        (time.perf_counter() - retrieval_started_at) * 1000,
    )

    anchor_rows = []
    if is_broad_document_question and (request.document_ids or request.case_id):
        anchor_stmt = (
            select(
                DocumentChunk.text_content,
                DocumentChunk.document_id,
                DocumentChunk.page_number,
                DocumentChunk.chunk_index,
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .order_by(DocumentChunk.document_id, DocumentChunk.page_number, DocumentChunk.chunk_index)
        )
        if org_id is not None:
            anchor_stmt = anchor_stmt.where(Document.organization_id == org_id)
        else:
            anchor_stmt = anchor_stmt.where(Document.uploaded_by_user_id == current_user.id)
        if request.case_id:
            anchor_stmt = anchor_stmt.where(Document.case_id == request.case_id)
        if request.document_ids:
            anchor_stmt = anchor_stmt.where(Document.id.in_(request.document_ids))

        anchor_res = await db.execute(anchor_stmt.limit(24))
        anchor_rows = [(row[0], row[1], row[2], row[3], 0.35) for row in anchor_res.all()]
        logger.info("AskAI[%s] anchor rows=%s broad=%s", request_id, len(anchor_rows), is_broad_document_question)

    # Fallback for unchunked documents that only have Document.content populated
    fallback_rows = []
    if not candidate_rows:
        doc_stmt = select(Document.id, Document.content).where(Document.content.isnot(None))
        if org_id is not None:
            doc_stmt = doc_stmt.where(Document.organization_id == org_id)
        else:
            doc_stmt = doc_stmt.where(Document.uploaded_by_user_id == current_user.id)
        if request.case_id:
            doc_stmt = doc_stmt.where(Document.case_id == request.case_id)
        if request.document_ids:
            doc_stmt = doc_stmt.where(Document.id.in_(request.document_ids))
        doc_res = await db.execute(doc_stmt.limit(10))
        for doc_id, full_content in doc_res.all():
            if full_content:
                # Synthetic chunking of full document content
                step = 1200
                for idx, offset in enumerate(range(0, len(full_content), step)):
                    snippet = full_content[offset:offset + step]
                    fallback_rows.append((snippet, doc_id, idx + 1, idx, 0.5))

    rows_to_rank = list(candidate_rows if candidate_rows else fallback_rows)
    if anchor_rows:
        seen_rows = {(row[1], row[2], row[3]) for row in rows_to_rank}
        rows_to_rank.extend(row for row in anchor_rows if (row[1], row[2], row[3]) not in seen_rows)
    if not rows_to_rank:
        return AskAIResponse(
            answer="Not found in documents. I don't have enough context to answer this question.",
            citations=[]
        )

    # Hybrid RAG Ranking: combine Vector Cosine Similarity + Lexical Keyword Match + Title/Header Position Boost
    keywords = _extract_query_keywords(request.question)
    scored = []
    for row in rows_to_rank:
        text_content = row[0] or ""
        doc_id = row[1]
        page = row[2]
        chunk_idx = row[3]
        distance = row[4]
        dist_val = distance if distance is not None else 1.0
        vec_score = max(0.0, 1.0 - dist_val)

        kw_hits = sum(1 for kw in keywords if kw in text_content)
        kw_score = kw_hits / max(1, len(keywords)) if keywords else 0.0

        pos_boost = 0.18 if (page and page <= 3) or (chunk_idx is not None and chunk_idx < 3) else 0.0

        hybrid_score = (vec_score * 0.52) + (kw_score * 0.38) + pos_boost
        scored.append((hybrid_score, text_content, doc_id, page, chunk_idx))

    scored.sort(key=lambda x: x[0], reverse=True)
    context_limit = min(max(request.top_k, 10), 12) if is_broad_document_question else min(request.top_k, 6)
    top_candidates = scored[:context_limit]
    # Sort selected snippets in logical document reading order
    top_candidates.sort(key=lambda x: (x[2], x[3] or 0, x[4] or 0))

    # 3. Context Construction
    context_parts = []
    citations_map = {} # document_id -> set(pages)

    for i, item in enumerate(top_candidates):
        _, text_content, doc_id, page, _ = item
        context_parts.append(f"--- SOURCE {i+1} (Doc ID: {doc_id}, Page: {page or 'N/A'}) ---\n{text_content}")
        
        if doc_id not in citations_map:
            citations_map[doc_id] = set()
        if page:
            citations_map[doc_id].add(page)

    context_str = "\n\n".join(context_parts)

    # 4. LLM Answer Generation
    is_hebrew_question = _is_hebrew(request.question)
    lang_hint = "You MUST answer in Hebrew." if is_hebrew_question else "You MUST answer in the same language as the user's question."
    route_intent, route_risk, requires_citations = _routing_for_ask_ai_intent(intent)
    document_ids = list(dict.fromkeys(request.document_ids or sorted({item[2] for item in top_candidates})))
    document_brief = await _load_document_brief(db, document_ids, case_obj)
    json_prompt = build_ask_ai_json_prompt(
        question=request.question,
        retrieved_context=context_str,
        document_brief=document_brief,
        intent=intent,
        lang_hint=lang_hint,
    )

    try:
        logger.info(
            "AskAI[%s] generation start intent=%s route_intent=%s risk=%s timeout_s=%.1f context_chars=%s brief_chars=%s",
            request_id,
            intent.value,
            route_intent.value if hasattr(route_intent, "value") else route_intent,
            route_risk.value if hasattr(route_risk, "value") else route_risk,
            timeout_seconds,
            len(context_str),
            len(document_brief),
        )
        generation_started_at = time.perf_counter()
        structured_response = await asyncio.wait_for(
            llm_service.generate_json(
                json_prompt,
                db=db,
                organization_id=org_id,
                task_type=f"reader.ask_ai.{intent.value}.json",
                intent=route_intent,
                feature="ask_ai",
                language="he" if is_hebrew_question else "",
                risk_level=route_risk,
                requires_citations=requires_citations,
            ),
            timeout=timeout_seconds,
        )

        if structured_response:
            ai_response = render_ask_ai_answer(structured_response, hebrew=is_hebrew_question)
            logger.info(
                "AskAI[%s] json generation done elapsed_ms=%.1f",
                request_id,
                (time.perf_counter() - generation_started_at) * 1000,
            )
        else:
            fallback_prompt = build_ask_ai_prompt(
                question=request.question,
                retrieved_context=context_str,
                document_brief=document_brief,
                intent=intent,
                lang_hint=lang_hint,
            )
            logger.info("AskAI[%s] json generation empty; trying text fallback", request_id)
            fallback_started_at = time.perf_counter()
            ai_response = await asyncio.wait_for(
                llm_service.generate_text(
                    fallback_prompt,
                    db=db,
                    organization_id=org_id,
                    task_type=f"reader.ask_ai.{intent.value}.text",
                    intent=route_intent,
                    feature="ask_ai",
                    language="he" if is_hebrew_question else "",
                    risk_level=route_risk,
                    requires_citations=requires_citations,
                ),
                timeout=min(timeout_seconds, 20.0),
            )
        
            logger.info(
                "AskAI[%s] text fallback done elapsed_ms=%.1f",
                request_id,
                (time.perf_counter() - fallback_started_at) * 1000,
            )

        if not ai_response:
            logger.warning("AskAI[%s] no AI response elapsed_ms=%.1f", request_id, (time.perf_counter() - started_at) * 1000)
            return AskAIResponse(answer="AI service is currently unavailable.", citations=[])

        # Parse citations from the hit list for the response object
        # In a real production system, we might ask the LLM to return JSON with citations.
        # For now, we provide the citations of the sources we found to be relevant.
        
        final_citations = []
        for doc_id, pages in citations_map.items():
            if not pages:
                final_citations.append(Citation(document_id=doc_id, page=None))
            else:
                for p in sorted(list(pages)):
                    final_citations.append(Citation(document_id=doc_id, page=p))

        response_obj = AskAIResponse(
            answer=ai_response,
            citations=final_citations
        )

        # 5. Caching
        await set_cache(cache_key, response_obj.model_dump())

        logger.info(
            "AskAI[%s] success citations=%s elapsed_ms=%.1f",
            request_id,
            len(final_citations),
            (time.perf_counter() - started_at) * 1000,
        )
        return response_obj

    except AIQuotaExceeded as exc:
        raise _quota_http_exception(exc)
    except asyncio.TimeoutError:
        logger.warning("AskAI[%s] timed out elapsed_ms=%.1f", request_id, (time.perf_counter() - started_at) * 1000)
        raise HTTPException(
            status_code=504,
            detail="AI Q&A timed out while generating the answer. Please try again in a moment.",
        )
    except Exception as e:
        logger.exception("AskAI[%s] error elapsed_ms=%.1f: %s", request_id, (time.perf_counter() - started_at) * 1000, e)
        raise HTTPException(status_code=500, detail="Error generating AI answer")
