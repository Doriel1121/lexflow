from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, HttpUrl, Field

from app.schemas.tag import Tag 
from app.schemas.summary import Summary
from app.schemas.document_metadata import DocumentMetadata
from app.db.models.document import DocumentProcessingStatus

class DocumentBase(BaseModel):
    filename: str
    s3_url: HttpUrl
    case_id: Optional[int] = None
    content: Optional[str] = None
    classification: Optional[str] = None
    language: Optional[str] = None
    page_count: Optional[int] = None
    processing_status: Optional[DocumentProcessingStatus] = None
    processing_stage: Optional[str] = None
    processing_progress: Optional[float] = None

class DocumentCreate(DocumentBase):
    pass

class DocumentUpdate(DocumentBase):
    filename: Optional[str] = None
    s3_url: Optional[HttpUrl] = None
    case_id: Optional[int] = None

class Document(DocumentBase):
    id: int
    uploaded_by_user_id: int
    created_at: datetime
    updated_at: datetime
    tags: List[Tag] = []
    summary: Optional[Summary] = None
    metadata: Optional[DocumentMetadata] = Field(None, validation_alias="document_metadata", serialization_alias="metadata")

    class Config:
        from_attributes = True
        populate_by_name = True
