from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class SummaryBase(BaseModel):
    document_id: int
    content: str
    key_dates: Optional[List[Any]] = None
    parties: Optional[List[str]] = None
    missing_documents: Optional[str] = Field(None, validation_alias="missing_documents_suggestion", serialization_alias="missing_documents")

class SummaryCreate(BaseModel):
    document_id: int
    content: str
    key_dates: Optional[List[Any]] = None
    parties: Optional[List[str]] = None
    missing_documents: Optional[str] = Field(None, validation_alias="missing_documents_suggestion", serialization_alias="missing_documents")

class SummaryUpdate(BaseModel):
    content: Optional[str] = None
    key_dates: Optional[List[Any]] = None
    parties: Optional[List[str]] = None
    missing_documents: Optional[str] = Field(None, validation_alias="missing_documents_suggestion", serialization_alias="missing_documents")

class Summary(SummaryBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True
