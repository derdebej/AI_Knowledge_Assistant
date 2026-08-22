"""pgvector-backed adapter implementing the `VectorStore` port.

See specs/DATABASE.md §5-6 for the HNSW/cosine-distance rationale and
specs/RAG_PIPELINE.md §2.3 for the Top-K/threshold/scoping contract - this
adapter runs the ANN query and returns ordered candidates; the caller
(`RetrievalService`) applies the relevance threshold.
"""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import RetrievedChunk
from app.models.chunk import DocumentChunk
from app.models.document import Document


class PgVectorStore:
    """Implements the `VectorStore` port."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_embeddings(self, chunk_ids: list[str], embeddings: list[list[float]]) -> None:
        for chunk_id, embedding in zip(chunk_ids, embeddings, strict=True):
            await self._session.execute(
                update(DocumentChunk)
                .where(DocumentChunk.id == uuid.UUID(chunk_id))
                .values(embedding=embedding)
            )
        await self._session.flush()

    async def similarity_search(
        self,
        query_embedding: list[float],
        *,
        user_id: str,
        document_ids: list[str] | None,
        top_k: int,
    ) -> list[RetrievedChunk]:
        # pgvector's `<=>` cosine-distance operator; similarity = 1 - distance.
        distance = DocumentChunk.embedding.cosine_distance(query_embedding)
        stmt = (
            select(DocumentChunk, distance.label("distance"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.user_id == uuid.UUID(user_id), DocumentChunk.embedding.isnot(None))
        )
        if document_ids:
            stmt = stmt.where(DocumentChunk.document_id.in_(uuid.UUID(d) for d in document_ids))
        stmt = stmt.order_by(distance).limit(top_k)

        result = await self._session.execute(stmt)
        return [
            RetrievedChunk(
                chunk_id=str(chunk.id),
                document_id=str(chunk.document_id),
                content=chunk.content,
                similarity_score=1.0 - distance_value,
                metadata=chunk.chunk_metadata,
            )
            for chunk, distance_value in result.all()
        ]
