"""In-memory test doubles for the RAG ports. See specs/TESTING.md §5.

Kept under `tests/`, not `app/` - these are test-only and never shipped;
`app/core/di.py` never references them. Integration test fixtures wire them
in directly (e.g. via `app.dependency_overrides` / explicit construction),
the same swap-the-adapter mechanism used for the real ones.
"""

import hashlib
import math
import uuid
from dataclasses import dataclass, field

from app.domain.entities import RetrievedChunk


class FakeEmbeddingProvider:
    """Deterministic hash-based pseudo-embeddings: the same input always
    yields the same vector, distinct inputs yield distinct vectors, so
    similarity ordering in tests is stable and assertable - without any real
    network call."""

    def __init__(self, dimensions: int = 1536) -> None:
        self._dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        raw: list[float] = []
        seed = text.encode("utf-8")
        counter = 0
        while len(raw) < self._dimensions:
            digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
            raw.extend(byte / 255.0 for byte in digest)
            counter += 1
        vector = raw[: self._dimensions]
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


@dataclass
class _StoredChunk:
    chunk_id: str
    document_id: str
    user_id: str
    content: str
    embedding: list[float]
    metadata: dict[str, object] = field(default_factory=dict)


class FakeVectorStore:
    """Brute-force in-memory cosine similarity backed by a Python list -
    exercises the same Top-K/scoping contract as `PgVectorStore` without a
    real database."""

    def __init__(self) -> None:
        self._chunks: list[_StoredChunk] = []

    def seed(
        self,
        *,
        document_id: str,
        user_id: str,
        content: str,
        embedding: list[float],
        chunk_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> str:
        chunk_id = chunk_id or str(uuid.uuid4())
        self._chunks.append(
            _StoredChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                user_id=user_id,
                content=content,
                embedding=embedding,
                metadata=metadata or {},
            )
        )
        return chunk_id

    async def upsert_embeddings(self, chunk_ids: list[str], embeddings: list[list[float]]) -> None:
        by_id = {chunk.chunk_id: chunk for chunk in self._chunks}
        for chunk_id, embedding in zip(chunk_ids, embeddings, strict=True):
            if chunk_id in by_id:
                by_id[chunk_id].embedding = embedding

    async def similarity_search(
        self,
        query_embedding: list[float],
        *,
        user_id: str,
        document_ids: list[str] | None,
        top_k: int,
    ) -> list[RetrievedChunk]:
        candidates = [chunk for chunk in self._chunks if chunk.user_id == user_id]
        if document_ids is not None:
            candidates = [chunk for chunk in candidates if chunk.document_id in document_ids]

        scored = [
            (chunk, _cosine_similarity(query_embedding, chunk.embedding)) for chunk in candidates
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                content=chunk.content,
                similarity_score=score,
                metadata=chunk.metadata,
            )
            for chunk, score in scored[:top_k]
        ]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
