import re
from typing import Optional


class TextNormalizationService:
    """
    Lightweight text normalization for OCR / PDF extracted content.

    Goals:
      - Remove obvious noise such as repeated page numbers and standalone
        "Page X" lines.
      - Collapse excessive whitespace and blank lines.
      - Preserve paragraph and page boundaries so downstream chunking can
        keep a stable notion of pages.

    The input is a single string which may contain the page break marker
    '--- Page Break ---' between logical pages.
    """

    PAGE_BREAK_MARKER = "--- Page Break ---"

    _page_number_re = re.compile(
        r"^\s*(page\s+\d+|p\.\s*\d+|\d+)\s*$",
        re.IGNORECASE,
    )

    def normalize(self, text: str, language: Optional[str] = None) -> str:
        if not text:
            return ""

        pages = text.split(f"\n\n{self.PAGE_BREAK_MARKER}\n\n")
        norm_pages = []

        for page in pages:
            lines = page.splitlines()
            cleaned_lines = []
            for line in lines:
                # Drop pure page-number lines
                if self._page_number_re.match(line or ""):
                    continue
                cleaned_lines.append(line.rstrip())

            # Collapse multiple consecutive blank lines
            compact_lines = []
            blank_streak = 0
            for line in cleaned_lines:
                if line.strip() == "":
                    blank_streak += 1
                    if blank_streak > 2:
                        continue
                else:
                    blank_streak = 0
                compact_lines.append(line)

            norm_pages.append("\n".join(compact_lines).strip())

        return f"\n\n{self.PAGE_BREAK_MARKER}\n\n".join(norm_pages).strip()


text_normalization_service = TextNormalizationService()

