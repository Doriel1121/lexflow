from pydantic import BaseModel

class DocumentText(BaseModel):
    id: int
    filename: str
    content: str
    language: str
    page_count: int
    
    class Config:
        from_attributes = True
