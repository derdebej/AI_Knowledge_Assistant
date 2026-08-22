"""Query-side pipeline: embed -> similarity search -> Top-K -> threshold
filter. See specs/RAG_PIPELINE.md §2.2-2.3.
"""

import uuid

from app.domain.entities import RetrievedChunk
from app.domain.ports import EmbeddingProvider, VectorStore


class RetrievalService:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        top_k: int,
        relevance_threshold: float,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._top_k = top_k
        self._relevance_threshold = relevance_threshold

    async def retrieve(
        self, question: str, *, user_id: uuid.UUID, document_ids: list[uuid.UUID] | None = None
    ) -> list[RetrievedChunk]:
        [query_embedding] = await self._embedding_provider.embed([question])
        candidates = await self._vector_store.similarity_search(
            query_embedding,
            user_id=str(user_id),
            document_ids=[str(document_id) for document_id in document_ids]
            if document_ids
            else None,
            top_k=self._top_k,
        )
        # Discarded even if within the top-K per specs/RAG_PIPELINE.md §2.3 -
        # a low-similarity "best available" chunk is worse than no chunk, and
        # an empty result here is what enables the "not found" short-circuit
        # (specs/RAG_PIPELINE.md §5), not an error condition on its own.
        return [
            chunk for chunk in candidates if chunk.similarity_score >= self._relevance_threshold
        ]
