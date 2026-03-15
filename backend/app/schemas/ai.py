from typing import List, Optional
from pydantic import BaseModel, Field

class Citation(BaseModel):
    document_id: int
    page: Optional[int] = None

class AskAIRequest(BaseModel):
    question: str = Field(..., example="What obligations does this contract create?")
    case_id: Optional[int] = None
    document_ids: Optional[List[int]] = None
    top_k: int = Field(8, ge=1, le=20)

class AskAIResponse(BaseModel):
    answer: str
    citations: List[Citation]
