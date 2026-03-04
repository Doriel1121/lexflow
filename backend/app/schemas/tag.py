from typing import Optional
from pydantic import BaseModel

class TagBase(BaseModel):
    name: str
    category: Optional[str] = None

class TagCreate(TagBase):
    pass

class TagUpdate(TagBase):
    name: Optional[str] = None
    category: Optional[str] = None

class Tag(TagBase):
    id: int
    document_count: int = 0

    class Config:
        from_attributes = True
