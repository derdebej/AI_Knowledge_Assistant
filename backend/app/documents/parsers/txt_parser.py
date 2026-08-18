"""Plain-text extraction. See specs/RAG_PIPELINE.md §1.2."""

from app.domain.entities import ExtractedDocument, ExtractedPage
from app.domain.exceptions import DocumentProcessingError, EmptyExtractionError


class TxtDocumentParser:
    """Implements the `DocumentParser` port for `.txt` files."""

    def extract(self, file_bytes: bytes) -> ExtractedDocument:
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = file_bytes.decode("latin-1")
            except UnicodeDecodeError as exc:
                raise DocumentProcessingError(f"Could not decode text file: {exc}") from exc

        if not text.strip():
            raise EmptyExtractionError("Text file is empty.")

        return ExtractedDocument(pages=[ExtractedPage(page_number=None, text=text)], page_count=None)
