"""Selects a `DocumentParser` adapter by content type. See specs/ARCHITECTURE.md §6."""

from app.documents.parsers.pdf_parser import PdfDocumentParser
from app.documents.parsers.txt_parser import TxtDocumentParser
from app.domain.exceptions import UnsupportedFileTypeError
from app.domain.ports import DocumentParser

_PARSERS: dict[str, DocumentParser] = {
    "application/pdf": PdfDocumentParser(),
    "text/plain": TxtDocumentParser(),
}


def get_parser(content_type: str) -> DocumentParser:
    parser = _PARSERS.get(content_type)
    if parser is None:
        raise UnsupportedFileTypeError(f"No parser registered for content type '{content_type}'.")
    return parser
