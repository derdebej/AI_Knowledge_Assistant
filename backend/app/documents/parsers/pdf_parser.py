"""PDF text extraction via pypdf (pure Python - no external binary dependency,
see specs/SECURITY.md §1). See specs/RAG_PIPELINE.md §1.2.
"""

import io

from pypdf import PdfReader

from app.domain.entities import ExtractedDocument, ExtractedPage
from app.domain.exceptions import DocumentProcessingError, EmptyExtractionError

# A page averaging fewer characters than this is treated as having no real
# text layer once summed across the document - see specs/RAG_PIPELINE.md §1.2.
_MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER = 10


class PdfDocumentParser:
    """Implements the `DocumentParser` port for `.pdf` files."""

    def extract(self, file_bytes: bytes) -> ExtractedDocument:
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
        except Exception as exc:
            raise DocumentProcessingError(f"Failed to open PDF: {exc}") from exc

        pages: list[ExtractedPage] = []
        for index, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                raise DocumentProcessingError(
                    f"Failed to extract text from page {index}: {exc}"
                ) from exc
            pages.append(ExtractedPage(page_number=index, text=text))

        total_chars = sum(len(page.text.strip()) for page in pages)
        if not pages or total_chars < _MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER * len(pages):
            raise EmptyExtractionError(
                "PDF appears to have no extractable text layer (scanned/image-only?). "
                "OCR is not supported in the MVP - see specs/ROADMAP.md Future improvements."
            )

        return ExtractedDocument(pages=pages, page_count=len(pages))
