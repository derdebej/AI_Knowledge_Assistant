"""Plain domain entities/value objects - no FastAPI, SQLAlchemy, or LangChain imports.

See specs/ARCHITECTURE.md §2.4.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExtractedPage:
    """A single page (or, for TXT, the whole document as one page) of raw extracted text."""

    page_number: int | None
    text: str


@dataclass(frozen=True)
class ExtractedDocument:
    """Result of DocumentParser.extract() - raw text plus page-level structure."""

    pages: list[ExtractedPage]
    page_count: int | None

    @property
    def full_text(self) -> str:
        return "\n\n".join(page.text for page in self.pages)


@dataclass(frozen=True)
class ChunkData:
    """A chunk produced by a Chunker, before persistence (no id, no embedding yet)."""

    chunk_index: int
    content: str
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievedChunk:
    """A chunk returned from vector similarity search, with its ranking score."""

    chunk_id: str
    document_id: str
    content: str
    similarity_score: float
    metadata: dict[str, Any]
