"""See specs/ARCHITECTURE.md §2.6 and specs/RAG_PIPELINE.md §1.7."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import ChunkData
from app.models.chunk import DocumentChunk


class ChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_all_for_document(
        self, document_id: uuid.UUID, chunks: list[ChunkData]
    ) -> list[DocumentChunk]:
        """Deletes any existing chunks for the document and inserts the given
        ones - keeps re-processing idempotent (specs/RAG_PIPELINE.md §1.7)."""
        await self._session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        rows = [
            DocumentChunk(
                document_id=document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                token_count=chunk.token_count,
                chunk_metadata=chunk.metadata,
            )
            for chunk in chunks
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return rows

    async def list_for_document(self, document_id: uuid.UUID) -> list[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
