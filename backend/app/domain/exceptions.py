"""Domain exceptions. See specs/ARCHITECTURE.md §2.4.

These carry business meaning and are translated to HTTP responses at the API
layer (specs/API.md §5) - the domain/service layers never raise HTTPException.
"""


class DomainError(Exception):
    """Base class for all domain-level errors."""


class UnsupportedFileTypeError(DomainError):
    """Raised when an uploaded file's extension or sniffed content type is not allowed."""


class FileTooLargeError(DomainError):
    """Raised when an uploaded file exceeds the configured size limit."""


class EmptyExtractionError(DomainError):
    """Raised when text extraction yields effectively no content.

    Covers e.g. scanned/image-only PDFs with no embedded text layer - see
    specs/RAG_PIPELINE.md §1.2. Not an OCR failure per se, just "nothing to index."
    """


class DocumentProcessingError(DomainError):
    """Raised when any ingestion pipeline stage fails for a reason other than the above."""


class DocumentNotFoundError(DomainError):
    """Raised when a document does not exist or does not belong to the requesting user."""


class NoRelevantContextError(DomainError):
    """Raised (or used as a signal) when retrieval finds no chunk above the relevance threshold.

    See specs/RAG_PIPELINE.md §5 - this is what triggers the "not found in your
    documents" short-circuit before any LLM call is made.
    """
