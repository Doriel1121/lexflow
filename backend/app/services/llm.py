from typing import List, Dict, Optional
import re
import json
import logging
from datetime import datetime, timedelta
from app.core.ai_router import AIIntent, AIRiskLevel, AITask, AITaskContext, ai_router
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_utils import is_zero_vector
from app.services.ai_quota import AIQuotaExceeded, enforce_ai_quota
from app.services.ai_usage_logger import track_ai_call

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        pass

    def _has_hebrew(self, text: str) -> bool:
        return any("֐" <= ch <= "׿" for ch in (text or "")[:4000])

    def _reader_context(
        self,
        *,
        prompt: str,
        task_type: str,
        intent: Optional[AIIntent | str] = None,
        feature: Optional[str] = None,
        language: Optional[str] = None,
        risk_level: Optional[AIRiskLevel | str] = None,
        requires_citations: bool = False,
    ) -> AITaskContext:
        lowered = (task_type or "").lower()
        inferred_intent: AIIntent | str = intent or AIIntent.GENERAL
        if intent is None:
            if "ask" in lowered and ("legal" in lowered or "reason" in lowered):
                inferred_intent = AIIntent.LEGAL_REASONING
            elif "ask" in lowered or "qa" in lowered or "question" in lowered:
                inferred_intent = AIIntent.DOCUMENT_QA
            elif "analysis" in lowered or "extract" in lowered or "json" in lowered:
                inferred_intent = AIIntent.DOCUMENT_ANALYSIS
            elif "summary" in lowered or "summar" in lowered:
                inferred_intent = AIIntent.SUMMARIZATION
            elif "classif" in lowered or "tag" in lowered:
                inferred_intent = AIIntent.CLASSIFICATION
        inferred_language = language or ("he" if self._has_hebrew(prompt) else "")
        inferred_risk = risk_level or (
            AIRiskLevel.HIGH
            if inferred_intent == AIIntent.LEGAL_REASONING or "legal" in lowered
            else AIRiskLevel.MEDIUM
        )
        return AITaskContext(
            task=AITask.READER,
            feature=feature or lowered.split(".", 1)[0] or "llm",
            intent=inferred_intent,
            language=inferred_language,
            input_chars=len(prompt or ""),
            risk_level=inferred_risk,
            requires_citations=requires_citations,
        )

    def _embedding_context(self, *, text: str, task_type: str) -> AITaskContext:
        return AITaskContext(
            task=AITask.EMBEDDING,
            feature=(task_type or "embedding").split(".", 1)[0],
            intent=AIIntent.EMBEDDING,
            language="he" if self._has_hebrew(text) else "",
            input_chars=len(text or ""),
            risk_level=AIRiskLevel.LOW,
        )
    
    async def summarize_text(self, text: str, length: str = "medium") -> str:
        prompt = f"Summarize this legal document concisely:\n\n{text[:4000]}"
        provider = ai_router.provider_for(
            AITask.READER,
            self._reader_context(
                prompt=prompt,
                task_type="reader.summary",
                intent=AIIntent.SUMMARIZATION,
                risk_level=AIRiskLevel.LOW,
            ),
        )
        try:
            if not provider.active:
                return f"Summary: {text[:300]}..."
            response_text = await provider.generate_text(prompt)
            return response_text if response_text else f"Summary: {text[:300]}... [AI unavailable]"
        except Exception:
            return f"Summary: {text[:300]}... [AI error]"

    async def generate_embedding(
        self,
        text: str,
        *,
        db: Optional[AsyncSession] = None,
        organization_id: Optional[int] = None,
        task_type: str = "embedding.document_chunk",
        input_type: Optional[str] = None,
    ) -> Optional[List[float]]:
        """Return embedding vector, or None if provider inactive or call failed."""
        try:
            embedding_provider = ai_router.provider_for(
                AITask.EMBEDDING,
                self._embedding_context(text=text, task_type=task_type),
            )
            if not embedding_provider.active:
                return None
            await enforce_ai_quota(
                db,
                organization_id=organization_id,
                task_type=task_type,
                input_chars=len(text or ""),
            )
            effective_input_type = input_type or ("search_query" if ("query" in task_type or "ask" in task_type) else "search_document")
            async with track_ai_call(
                db,
                organization_id=organization_id,
                task_type=task_type,
                provider=embedding_provider,
                input_text=text,
            ) as usage:
                import inspect
                fn_params = inspect.signature(embedding_provider.generate_embedding).parameters
                if "input_type" in fn_params:
                    vector = await embedding_provider.generate_embedding(text, input_type=effective_input_type)
                else:
                    vector = await embedding_provider.generate_embedding(text)
                usage["output_chars"] = len(vector or [])
            if is_zero_vector(vector):
                return None
            return vector
        except AIQuotaExceeded:
            raise
        except Exception as e:
            logger.warning("Error generating embedding: %s", e)
            return None

    async def generate_embeddings(
        self,
        texts: List[str],
        *,
        db: Optional[AsyncSession] = None,
        organization_id: Optional[int] = None,
        task_type: str = "embedding.document_chunk_batch",
    ) -> List[Optional[List[float]]]:
        """Batch embeddings when supported by provider; falls back to per-text."""
        if not texts:
            return []
        embedding_provider = ai_router.provider_for(
            AITask.EMBEDDING,
            AITaskContext(
                task=AITask.EMBEDDING,
                feature=(task_type or "embedding").split(".", 1)[0],
                intent=AIIntent.EMBEDDING,
                language="he" if any(self._has_hebrew(t) for t in texts) else "",
                input_chars=sum(len(t or "") for t in texts),
                risk_level=AIRiskLevel.LOW,
            ),
        )
        if not embedding_provider.active:
            return [None for _ in texts]
        await enforce_ai_quota(
            db,
            organization_id=organization_id,
            task_type=task_type,
            input_chars=sum(len(t or "") for t in texts),
        )

        batch_fn = getattr(embedding_provider, "generate_embeddings", None)
        if callable(batch_fn):
            try:
                async with track_ai_call(
                    db,
                    organization_id=organization_id,
                    task_type=task_type,
                    provider=embedding_provider,
                    input_chars=sum(len(t or "") for t in texts),
                ) as usage:
                    vectors = await batch_fn(texts)
                    usage["output_chars"] = sum(len(v or []) for v in vectors or [])
                out: List[Optional[List[float]]] = []
                for v in vectors:
                    out.append(None if is_zero_vector(v) else v)
                # Be defensive if provider returns wrong length.
                if len(out) != len(texts):
                    out = (out + [None for _ in range(len(texts))])[: len(texts)]
                return out
            except Exception as e:
                logger.warning("Error generating batch embeddings: %s", e)

        # Fallback: sequential per-text (still safe, just slower / more requests).
        out: List[Optional[List[float]]] = []
        for t in texts:
            out.append(
                await self.generate_embedding(
                    t,
                    db=db,
                    organization_id=organization_id,
                    task_type=task_type,
                )
            )
        return out

    async def generate_text(
        self,
        prompt: str,
        *,
        db: Optional[AsyncSession] = None,
        organization_id: Optional[int] = None,
        task_type: str = "reader.text_generation",
        intent: Optional[AIIntent | str] = None,
        feature: Optional[str] = None,
        language: Optional[str] = None,
        risk_level: Optional[AIRiskLevel | str] = None,
        requires_citations: bool = False,
    ) -> Optional[str]:
        provider = ai_router.provider_for(
            AITask.READER,
            self._reader_context(
                prompt=prompt,
                task_type=task_type,
                intent=intent,
                feature=feature,
                language=language,
                risk_level=risk_level,
                requires_citations=requires_citations,
            ),
        )
        if not provider.active:
            return None
        await enforce_ai_quota(
            db,
            organization_id=organization_id,
            task_type=task_type,
            input_chars=len(prompt or ""),
        )
        async with track_ai_call(
            db,
            organization_id=organization_id,
            task_type=task_type,
            provider=provider,
            input_text=prompt,
        ) as usage:
            response_text = await provider.generate_text(prompt)
            usage["output_chars"] = len(response_text or "")
            return response_text

    async def generate_json(
        self,
        prompt: str,
        *,
        db: Optional[AsyncSession] = None,
        organization_id: Optional[int] = None,
        task_type: str = "reader.json_generation",
        intent: Optional[AIIntent | str] = None,
        feature: Optional[str] = None,
        language: Optional[str] = None,
        risk_level: Optional[AIRiskLevel | str] = None,
        requires_citations: bool = False,
    ) -> Optional[Dict[str, object]]:
        provider = ai_router.provider_for(
            AITask.READER,
            self._reader_context(
                prompt=prompt,
                task_type=task_type,
                intent=intent,
                feature=feature,
                language=language,
                risk_level=risk_level,
                requires_citations=requires_citations,
            ),
        )
        if not provider.active:
            return None
        await enforce_ai_quota(
            db,
            organization_id=organization_id,
            task_type=task_type,
            input_chars=len(prompt or ""),
        )
        async with track_ai_call(
            db,
            organization_id=organization_id,
            task_type=task_type,
            provider=provider,
            input_text=prompt,
        ) as usage:
            response_json = await provider.generate_json(prompt)
            usage["output_chars"] = len(json.dumps(response_json, ensure_ascii=False)) if response_json else 0
            return response_json

    async def extract_keywords(self, text: str, limit: int = 12) -> List[str]:
        """Lightweight keywords for routing (no extra LLM call)."""
        words = re.findall(r"\b[\w\u0590-\u05FF]{4,}\b", text or "")
        stop = {
            "from", "subject", "dear", "regards", "with", "that", "this", "have", "been",
            "document", "attachment", "please", "thank", "your", "הנדון", "בברכה",
        }
        seen, out = set(), []
        for w in words:
            key = w.lower()
            if key in stop or key in seen:
                continue
            seen.add(key)
            out.append(w)
            if len(out) >= limit:
                break
        return out

    async def extract_key_dates(self, text: str) -> List[Dict[str, str]]:
        """Extract UPCOMING legal deadlines only, excluding citations and irrelevant dates."""
        try:
            today = datetime.now()
            three_years_ago = (today - timedelta(days=3*365)).strftime("%Y-%m-%d")
            ten_years_future = (today + timedelta(days=10*365)).strftime("%Y-%m-%d")
            
            prompt = (
                "You are a legal document analyzer. Extract UPCOMING LEGAL DEADLINES only.\n\n"
                "CRITICAL RULES:\n"
                "1. Extract ONLY future/upcoming deadlines relevant to the case (filing deadlines, hearing dates, response dates, appeal deadlines)\n"
                "2. IGNORE and EXCLUDE:\n"
                f"   - Case law citations and legal references\n"
                f"   - Historical dates from past cases (dates before {three_years_ago})\n"
                f"   - Years that don't make sense ({today.year} +/- 10 years is valid range)\n"
                f"   - Dates way in the future (after {ten_years_future})\n"
                "   - Dates mentioned just as examples or in quoted text\n"
                "3. For each deadline: DATE (YYYY-MM-DD), TYPE (hearing/filing/response/appeal/statute_of_limitations/other), DESCRIPTION\n"
                "4. Be skeptical - ONLY include dates that are clearly ACTION DATES for THIS case\n"
                "5. Return ONLY valid deadlines within realistic range\n\n"
                "Document text:\n"
                f"{text[:3000]}\n\n"
                'Format: Return ONLY JSON array - [{"date": "YYYY-MM-DD", "type": "filing", "description": "context"}]\n\n'
                "If no valid deadlines, return []"
            )
            
            response_text = await self.generate_text(
                prompt,
                task_type="reader.deadline_extraction",
                intent=AIIntent.DOCUMENT_ANALYSIS,
                risk_level=AIRiskLevel.HIGH,
            )
            if not response_text:
                return []
            
            try:
                response_text = response_text.strip()
                if response_text.startswith("```"):
                    response_text = response_text.split("```")[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]
                
                deadlines = json.loads(response_text)
                validated = [d for d in deadlines if self._is_valid_deadline(d.get("date"))]
                return validated
            except json.JSONDecodeError:
                return []
        except:
            return []

    def _is_valid_deadline(self, date_str: str) -> bool:
        """Check if date is within realistic legal deadline range."""
        try:
            if not date_str:
                return False
            d_date = datetime.fromisoformat(date_str.split("T")[0])
            today = datetime.now()
            three_years_ago = today - timedelta(days=3*365)
            ten_years_future = today + timedelta(days=10*365)
            return three_years_ago <= d_date <= ten_years_future
        except:
            return False

    async def extract_parties(self, text: str) -> List[str]:
        try:
            response_text = await self.generate_text(
                f"Extract all party names (people, companies) from this legal text, return as comma-separated list:\n\n{text[:2000]}",
                task_type="reader.party_extraction",
                intent=AIIntent.DOCUMENT_ANALYSIS,
                risk_level=AIRiskLevel.MEDIUM,
            )
            if not response_text:
                return []
            return [p.strip() for p in response_text.split(",") if p.strip()]
        except Exception:
            return []

    async def suggest_missing_documents(self, case_context: str) -> str:
        try:
            response_text = await self.generate_text(
                f"Based on this case, suggest what documents might be missing:\n\n{case_context[:2000]}",
                task_type="reader.missing_documents",
                intent=AIIntent.LEGAL_REASONING,
                risk_level=AIRiskLevel.HIGH,
                requires_citations=True,
            )
            return response_text if response_text else "AI suggestions unavailable"
        except Exception:
            return "AI suggestions unavailable"

llm_service = LLMService()
