from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, HttpUrl

from app.schemas.tag import Tag # Assuming Tag schema exists
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

    class Config:
        from_attributes = True
