"""Embedding step wired into the ingestion pipeline, and end-to-end
retrieval on top of it - against a real Postgres+pgvector database with a
faked embedding provider. See specs/TESTING.md §3 and specs/ROADMAP.md
Phase 3.

Uses the `client` fixture (real API, real DB, `BackgroundTasks` run
synchronously - specs/TESTING.md conftest) so ingestion runs exactly as it
would in production, only the embedding provider is faked.
"""

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.chunk import DocumentChunk
from app.models.user import User
from app.rag.vector_store.pgvector_store import PgVectorStore
from app.services.retrieval_service import RetrievalService
from tests.fakes import FakeEmbeddingProvider

_KNOWN_CONTENT = b"The mitochondria is the powerhouse of the cell."


class TestIngestionStoresEmbeddings:
    async def test_uploaded_document_chunks_have_embeddings_after_completion(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        response = await client.post(
            "/api/v1/documents", files={"file": ("notes.txt", _KNOWN_CONTENT, "text/plain")}
        )
        document_id = response.json()["id"]

        detail = await client.get(f"/api/v1/documents/{document_id}")
        assert detail.json()["status"] == "completed"

        chunks = (
            (
                await db_session.execute(
                    select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(document_id))
                )
            )
            .scalars()
            .all()
        )
        assert len(chunks) >= 1
        assert all(chunk.embedding is not None for chunk in chunks)
        assert all(len(chunk.embedding) == get_settings().embedding_dimensions for chunk in chunks)


class TestRetrievalServiceEndToEnd:
    async def test_retrieve_returns_the_uploaded_chunk_for_a_matching_query(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        upload = await client.post(
            "/api/v1/documents", files={"file": ("notes.txt", _KNOWN_CONTENT, "text/plain")}
        )
        document_id = upload.json()["id"]

        # FakeEmbeddingProvider is deterministic - embedding the exact chunk
        # content again reproduces the same vector ingestion stored, giving a
        # real (not hash-coincidental) similarity match through the full
        # embed -> similarity-search -> threshold-filter pipeline.
        retrieval_service = RetrievalService(
            embedding_provider=FakeEmbeddingProvider(),
            vector_store=PgVectorStore(db_session),
            top_k=get_settings().retrieval_top_k,
            relevance_threshold=get_settings().relevance_threshold,
        )

        results = await retrieval_service.retrieve(_KNOWN_CONTENT.decode(), user_id=test_user.id)

        assert len(results) == 1
        assert results[0].document_id == document_id
        assert results[0].similarity_score >= get_settings().relevance_threshold

    async def test_retrieve_scoped_to_a_different_document_returns_nothing(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await client.post(
            "/api/v1/documents", files={"file": ("notes.txt", _KNOWN_CONTENT, "text/plain")}
        )
        other_document_id = uuid.uuid4()
        retrieval_service = RetrievalService(
            embedding_provider=FakeEmbeddingProvider(),
            vector_store=PgVectorStore(db_session),
            top_k=get_settings().retrieval_top_k,
            relevance_threshold=get_settings().relevance_threshold,
        )

        results = await retrieval_service.retrieve(
            _KNOWN_CONTENT.decode(), user_id=test_user.id, document_ids=[other_document_id]
        )

        assert results == []
