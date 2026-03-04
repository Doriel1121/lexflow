from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel

class DocumentMetadataBase(BaseModel):
    dates: Optional[List[Any]] = []  # List of date objects with context
    entities: Optional[List[Any]] = []  # List of person/org objects with IDs
    amounts: Optional[List[Any]] = []  # List of amount objects with description
    case_numbers: Optional[List[str]] = []

class DocumentMetadataCreate(DocumentMetadataBase):
    document_id: int

class DocumentMetadata(DocumentMetadataBase):
    id: int
    document_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
