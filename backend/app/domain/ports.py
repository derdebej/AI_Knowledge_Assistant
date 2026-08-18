"""Domain ports (interfaces) that infrastructure adapters implement.

See specs/ARCHITECTURE.md §2.4 and §6 for the full replaceability rationale.
Each port is a `Protocol` so adapters don't need to inherit from anything -
they just need to satisfy the shape, which keeps infrastructure code free to
use whatever base classes its underlying SDK requires.
"""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from app.domain.entities import ChunkData, ExtractedDocument, RetrievedChunk


@runtime_checkable
class DocumentParser(Protocol):
    """Extracts raw text (+ page structure) from an uploaded file's bytes.

    See specs/RAG_PIPELINE.md §1.2. One implementation per supported content
    type (PDF, TXT); specs/ARCHITECTURE.md §6 lists future adapters (OCR, etc).
    """

    def extract(self, file_bytes: bytes) -> ExtractedDocument: ...


@runtime_checkable
class Chunker(Protocol):
    """Splits cleaned text into chunks. See specs/RAG_PIPELINE.md §1.5 for parameters."""

    def split(
        self, text: str, *, base_metadata: dict[str, object] | None = None
    ) -> list[ChunkData]: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Turns text into vectors. Query and document embeddings MUST come from the
    same implementation/model - see specs/RAG_PIPELINE.md §2.2."""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class LLMProvider(Protocol):
    """Generates an answer from a fully-assembled prompt. See specs/RAG_PIPELINE.md §2.7."""

    async def generate(self, prompt: str) -> str: ...

    def stream(self, prompt: str) -> AsyncIterator[str]: ...


@runtime_checkable
class VectorStore(Protocol):
    """Persists chunk embeddings and performs similarity search.

    See specs/DATABASE.md §5-6 for the indexing/metric rationale and
    specs/RAG_PIPELINE.md §2.3 for the Top-K/threshold/filtering contract.
    """

    async def upsert_embeddings(self, chunk_ids: list[str], embeddings: list[list[float]]) -> None: ...

    async def similarity_search(
        self,
        query_embedding: list[float],
        *,
        user_id: str,
        document_ids: list[str] | None,
        top_k: int,
    ) -> list[RetrievedChunk]: ...
