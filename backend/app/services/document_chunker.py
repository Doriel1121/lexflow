import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class DocumentChunker:
    def __init__(self, max_chunk_size: int = 2000, overlap: int = 200):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    def chunk_document(self, text: str) -> List[Dict[str, str]]:
        """
        Splits a large document into intelligent chunks, preferring paragraph boundaries.
        Returns a list of dicts with 'index' and 'text'.
        """
        if not text:
            return []

        chunks = []
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        chunk_index = 0
        
        for para in paragraphs:
            # If a single paragraph is larger than max_chunk_size, we have to split it blindly
            if len(para) > self.max_chunk_size:
                # First flush current chunk if any
                if current_chunk:
                    chunks.append({"index": chunk_index, "text": current_chunk.strip()})
                    chunk_index += 1
                    current_chunk = ""
                
                # Split the huge paragraph by length
                for i in range(0, len(para), self.max_chunk_size - self.overlap):
                    sub_chunk = para[i:i + self.max_chunk_size]
                    chunks.append({"index": chunk_index, "text": sub_chunk.strip()})
                    chunk_index += 1
                continue
                
            # If adding this paragraph exceeds the chunk size, flush the current chunk
            if len(current_chunk) + len(para) + 2 > self.max_chunk_size:
                chunks.append({"index": chunk_index, "text": current_chunk.strip()})
                chunk_index += 1
                
                # Start new chunk with overlap from previous text (simplified by just starting new)
                current_chunk = para + "\n\n"
            else:
                current_chunk += para + "\n\n"
                
        # Flush the last chunk
        if current_chunk.strip():
            chunks.append({"index": chunk_index, "text": current_chunk.strip()})
            
        return chunks

document_chunker = DocumentChunker()
