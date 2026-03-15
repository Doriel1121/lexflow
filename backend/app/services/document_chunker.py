import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class DocumentChunker:
    def __init__(
        self,
        max_chunk_size: int = 2000,
        overlap: int = 200,
        page_break_marker: str = "--- Page Break ---",
    ):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        self.page_break_marker = page_break_marker

    def chunk_document(self, text: str) -> List[Dict[str, Any]]:
        """
        Splits a large document into intelligent chunks, preferring paragraph boundaries.

        The input text may contain explicit page break markers inserted by the OCR
        layer (e.g. '--- Page Break ---'). We preserve approximate page references
        by tracking which logical page each chunk primarily belongs to.

        Returns a list of dicts:
          { "index": int, "text": str, "page_number": Optional[int] }
        """
        if not text:
            return []

        # First, split into logical pages using the page break marker if present.
        raw_pages = []
        marker = self.page_break_marker
        if marker in text:
            raw_pages = text.split(f"\n\n{marker}\n\n")
        else:
            raw_pages = [text]

        chunks: List[Dict[str, Any]] = []
        chunk_index = 0

        for page_idx, page_text in enumerate(raw_pages, start=1):
            page_paragraphs = page_text.split("\n\n")
            current_chunk = ""

            for para in page_paragraphs:
                para = para.strip()
                if not para:
                    continue

                # If a single paragraph is larger than max_chunk_size, split it directly
                if len(para) > self.max_chunk_size:
                    if current_chunk:
                        chunks.append(
                            {
                                "index": chunk_index,
                                "text": current_chunk.strip(),
                                "page_number": page_idx,
                            }
                        )
                        chunk_index += 1
                        current_chunk = ""

                    for i in range(0, len(para), self.max_chunk_size - self.overlap):
                        sub_chunk = para[i : i + self.max_chunk_size]
                        chunks.append(
                            {
                                "index": chunk_index,
                                "text": sub_chunk.strip(),
                                "page_number": page_idx,
                            }
                        )
                        chunk_index += 1
                    continue

                # If adding this paragraph exceeds the chunk size, flush the current chunk
                if len(current_chunk) + len(para) + 2 > self.max_chunk_size:
                    if current_chunk.strip():
                        chunks.append(
                            {
                                "index": chunk_index,
                                "text": current_chunk.strip(),
                                "page_number": page_idx,
                            }
                        )
                        chunk_index += 1
                    current_chunk = para + "\n\n"
                else:
                    current_chunk += para + "\n\n"

            # Flush the last chunk for this page
            if current_chunk.strip():
                chunks.append(
                    {
                        "index": chunk_index,
                        "text": current_chunk.strip(),
                        "page_number": page_idx,
                    }
                )
                chunk_index += 1

        return chunks


document_chunker = DocumentChunker()
