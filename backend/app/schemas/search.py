from typing import List, Optional
from pydantic import BaseModel
from .document import Document
from .case import Case
from .client import Client

class GlobalSearchResult(BaseModel):
    documents: List[Document] = []
    cases: List[Case] = []
    clients: List[Client] = []
    
    @property
    def total_count(self) -> int:
        return len(self.documents) + len(self.cases) + len(self.clients)
