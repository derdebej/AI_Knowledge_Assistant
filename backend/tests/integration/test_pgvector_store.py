"""pgvector similarity search + index usage against a real Postgres+pgvector
database. See specs/TESTING.md §3 and specs/RAG_PIPELINE.md §2.3.
"""

import uuid

from sqlalchemy import select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.entities import ChunkData
from app.models.chunk import DocumentChunk
from app.models.user import User
from app.rag.vector_store.pgvector_store import PgVectorStore
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository

_DIMENSIONS = get_settings().embedding_dimensions


def _basis_vector(index: int) -> list[float]:
    """A unit vector with a 1.0 in position `index`, 0.0 elsewhere - cosine
    similarity between two basis vectors is exactly 1.0 for the same index,
    0.0 otherwise, which makes similarity ordering trivial to assert exactly."""
    vector = [0.0] * _DIMENSIONS
    vector[index] = 1.0
    return vector


async def _create_document_with_chunks(
    db_session: AsyncSession, user: User, chunk_embeddings: list[list[float]]
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    document = await document_repo.create(
        document_id=uuid.uuid4(),
        user_id=user.id,
        filename="report.pdf",
        original_filename="report.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        storage_path=f"/data/uploads/{uuid.uuid4()}/report.pdf",
    )
    chunks = [
        ChunkData(chunk_index=i, content=f"chunk {i}", token_count=1, metadata={})
        for i in range(len(chunk_embeddings))
    ]
    rows = await chunk_repo.replace_all_for_document(document.id, chunks)
    vector_store = PgVectorStore(db_session)
    await vector_store.upsert_embeddings([str(row.id) for row in rows], chunk_embeddings)
    await db_session.commit()
    return document.id, [row.id for row in rows]


class TestPgVectorStoreSimilaritySearch:
    async def test_orders_results_by_descending_cosine_similarity(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        document_id, chunk_ids = await _create_document_with_chunks(
            db_session, test_user, [_basis_vector(0), _basis_vector(1), _basis_vector(2)]
        )
        vector_store = PgVectorStore(db_session)

        results = await vector_store.similarity_search(
            _basis_vector(0), user_id=str(test_user.id), document_ids=None, top_k=10
        )

        assert [r.document_id for r in results] == [str(document_id)] * 3
        assert results[0].chunk_id == str(chunk_ids[0])
        assert results[0].similarity_score == 1.0
        assert results[1].similarity_score == 0.0
        assert results[2].similarity_score == 0.0

    async def test_respects_top_k(self, db_session: AsyncSession, test_user: User) -> None:
        await _create_document_with_chunks(
            db_session, test_user, [_basis_vector(0), _basis_vector(0), _basis_vector(0)]
        )
        vector_store = PgVectorStore(db_session)

        results = await vector_store.similarity_search(
            _basis_vector(0), user_id=str(test_user.id), document_ids=None, top_k=2
        )

        assert len(results) == 2

    async def test_scopes_by_user_id(self, db_session: AsyncSession, test_user: User) -> None:
        other_user = User(
            email=f"{uuid.uuid4()}@test.local", hashed_password="unused", is_active=True
        )
        db_session.add(other_user)
        await db_session.flush()
        await _create_document_with_chunks(db_session, other_user, [_basis_vector(0)])
        vector_store = PgVectorStore(db_session)

        results = await vector_store.similarity_search(
            _basis_vector(0), user_id=str(test_user.id), document_ids=None, top_k=10
        )

        assert results == []

    async def test_document_ids_filter_scopes_results(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        document_id_a, _ = await _create_document_with_chunks(
            db_session, test_user, [_basis_vector(0)]
        )
        await _create_document_with_chunks(db_session, test_user, [_basis_vector(0)])
        vector_store = PgVectorStore(db_session)

        results = await vector_store.similarity_search(
            _basis_vector(0),
            user_id=str(test_user.id),
            document_ids=[str(document_id_a)],
            top_k=10,
        )

        assert [r.document_id for r in results] == [str(document_id_a)]

    async def test_chunks_without_embeddings_are_excluded(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        document_repo = DocumentRepository(db_session)
        chunk_repo = ChunkRepository(db_session)
        document = await document_repo.create(
            document_id=uuid.uuid4(),
            user_id=test_user.id,
            filename="report.pdf",
            original_filename="report.pdf",
            content_type="application/pdf",
            file_size_bytes=1024,
            storage_path=f"/data/uploads/{uuid.uuid4()}/report.pdf",
        )
        await chunk_repo.replace_all_for_document(
            document.id,
            [ChunkData(chunk_index=0, content="not yet embedded", token_count=1, metadata={})],
        )
        await db_session.commit()
        vector_store = PgVectorStore(db_session)

        results = await vector_store.similarity_search(
            _basis_vector(0), user_id=str(test_user.id), document_ids=None, top_k=10
        )

        assert results == []


class TestPgVectorStoreIndexUsage:
    async def test_similarity_search_uses_the_hnsw_index(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        await _create_document_with_chunks(
            db_session, test_user, [_basis_vector(0), _basis_vector(1)]
        )

        # Postgres' planner reasonably prefers a sequential scan over an ANN
        # index on a table this small - forcing seqscan off is the standard
        # way to prove the index *can* be selected and is wired up correctly
        # (name, column, opclass), independent of table size.
        await db_session.execute(text("SET LOCAL enable_seqscan = off"))

        stmt = (
            select(DocumentChunk.id)
            .where(DocumentChunk.embedding.isnot(None))
            .order_by(DocumentChunk.embedding.cosine_distance(_basis_vector(0)))
            .limit(5)
        )
        compiled_sql = str(
            stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )
        plan_rows = (await db_session.execute(text(f"EXPLAIN {compiled_sql}"))).all()
        plan_text = "\n".join(row[0] for row in plan_rows)

        assert "idx_chunks_embedding_hnsw" in plan_text
