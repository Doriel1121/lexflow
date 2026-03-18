import json
import logging
import hashlib
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.api import deps
from app.db.models.document import Document, DocumentChunk
from app.db.models.case import Case
from app.db.models.user import User as DBUser, UserRole
from app.schemas.ai import AskAIRequest, AskAIResponse, Citation
from app.services.llm import llm_service
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Basic Redis setup for caching
redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True) if hasattr(settings, "REDIS_URL") else None
CACHE_TTL = 3600  # 1 hour

async def get_cache(key: str) -> Optional[Dict[str, Any]]:
    if not redis_client:
        return None
    try:
        cached = await redis_client.get(key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Cache get error: {e}")
    return None

async def set_cache(key: str, value: Dict[str, Any]):
    if not redis_client:
        return
    try:
        await redis_client.setex(key, CACHE_TTL, json.dumps(value))
    except Exception as e:
        logger.warning(f"Cache set error: {e}")

def generate_cache_key(request: AskAIRequest, org_id: Optional[int]) -> str:
    # Stable hash of request parameters
    req_data = f"{request.question}:{request.case_id}:{request.document_ids}:{request.top_k}:{org_id}"
    return f"rag:query:{hashlib.md5(req_data.encode()).hexdigest()}"

def _is_hebrew(text: str) -> bool:
    for ch in text:
        if "\u0590" <= ch <= "\u05FF":
            return True
    return False

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
    # 1. Security & Validation
    cache_key = generate_cache_key(request, org_id)
    cached_res = await get_cache(cache_key)
    if cached_res:
        return AskAIResponse(**cached_res)

    # Validate Case Access if provided
    if request.case_id:
        case = await db.get(Case, request.case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        deps.verify_resource_access(case, current_user)

    # 2. Semantic Retrieval
    # Generate embedding for the question
    question_vector = await llm_service.generate_embedding(request.question)
    
    # Construct query with pgvector cosine distance
    # We join with Document to ensure org/user isolation
    stmt = (
        select(
            DocumentChunk.text_content,
            DocumentChunk.document_id,
            DocumentChunk.page_number,
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

    # Order by similarity and limit
    stmt = stmt.order_by("distance").limit(request.top_k)
    
    result = await db.execute(stmt)
    hits = result.all()

    if not hits:
        return AskAIResponse(
            answer="Not found in documents. I don't have enough context to answer this question.",
            citations=[]
        )

    # 3. Context Construction
    context_parts = []
    citations_map = {} # document_id -> set(pages)

    for i, hit in enumerate(hits):
        text_content, doc_id, page, distance = hit
        context_parts.append(f"--- SOURCE {i+1} (Doc ID: {doc_id}, Page: {page or 'N/A'}) ---\n{text_content}")
        
        if doc_id not in citations_map:
            citations_map[doc_id] = set()
        if page:
            citations_map[doc_id].add(page)

    context_str = "\n\n".join(context_parts)

    # 4. LLM Answer Generation
    # We improve the prompt to be much stricter about formatting and quality
    lang_hint = ""
    if _is_hebrew(request.question):
        lang_hint = "You MUST answer in Hebrew."
    else:
        lang_hint = "You MUST answer in the same language as the user's question."

    prompt = f"""You are a professional legal analyst. Answer the user's QUESTION based strictly on the provided CONTEXT.

CONTEXT:
{context_str}

USER QUESTION:
{request.question}

INSTRUCTIONS:
1. Provide a clear, professional, and well-structured answer. {lang_hint}
2. Use bullet points for lists of obligations, dates, or key facts.
3. Do NOT include technical Source IDs (like "Source 1") or Document IDs in the middle of your sentences. 
4. Do NOT repeat yourself or use unnecessary symbols/parentheses.
5. If the context does not contain the answer, say: "I'm sorry, but I couldn't find the information regarding this in the provided documents."
6. Ground every claim in the text. Do not hallucinate or add outside legal knowledge.
"""

    try:
        # We use summarize_text's underlying provider or just a generic call if available.
        # LLMService doesn't have a generic 'ask' yet, so let's add one or use provider directly.
        ai_response = await llm_service.provider.generate_text(prompt)
        
        if not ai_response:
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

        return response_obj

    except Exception as e:
        logger.error(f"RAG error: {e}")
        raise HTTPException(status_code=500, detail="Error generating AI answer")
