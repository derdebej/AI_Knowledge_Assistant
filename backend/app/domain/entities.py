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


@dataclass(frozen=True)
class Citation:
    """A chunk that was included in the prompt shown to the model, with its
    rank and score - reflects what was shown to the model, not a claim about
    which specific sentence it drew from (specs/RAG_PIPELINE.md §2.8).

    `document_name`/`page_number` are carried here (denormalized from the
    chunk's metadata, same as `RetrievedChunk`) so both the SSE `citations`
    event and the persisted-message display shape (specs/API.md §3) can be
    built from this one entity without a second DB round-trip.

    Carries no `message_id`: that's only assigned when a message is actually
    persisted (as a `message_citations` row - specs/DATABASE.md §3.7), which
    is outside ChatService's concern (specs/ROADMAP.md Phase 4 vs Phase 5).
    """

    chunk_id: str
    document_id: str
    document_name: str
    page_number: int | None
    similarity_score: float
    rank: int


@dataclass(frozen=True)
class ChatAnswer:
    """Result of `ChatService.ask()` - independent of the API/streaming layer."""

    content: str
    citations: list[Citation]


@dataclass(frozen=True)
class ChatStreamEvent:
    """One SSE frame's worth of data, still framework-free - the API layer
    (specs/ARCHITECTURE.md §2.1) is what knows how to format this as
    `event: ...\\ndata: ...` wire bytes. `event` is one of "token",
    "citations", or "done" (specs/API.md §3); "error" is added by the API
    layer itself when generation fails, not yielded from here."""

    event: str
    data: dict[str, Any]
