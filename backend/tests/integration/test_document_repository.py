"""Repository CRUD + cascade delete against a real Postgres+pgvector
database. See specs/TESTING.md §3."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import ChunkData
from app.models.chunk import DocumentChunk
from app.models.document import DocumentStatus
from app.models.user import User
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository


async def _create_document(repo: DocumentRepository, user: User, *, filename: str = "report.pdf"):
    return await repo.create(
        document_id=uuid.uuid4(),
        user_id=user.id,
        filename=filename,
        original_filename=filename,
        content_type="application/pdf",
        file_size_bytes=1024,
        storage_path=f"/data/uploads/{uuid.uuid4()}/{filename}",
    )


class TestDocumentRepository:
    async def test_create_and_get_by_id(self, db_session: AsyncSession, test_user: User) -> None:
        repo = DocumentRepository(db_session)
        created = await _create_document(repo, test_user)
        await db_session.commit()

        fetched = await repo.get_by_id(created.id, user_id=test_user.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.status == DocumentStatus.PENDING

    async def test_get_by_id_scoped_to_owner(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        repo = DocumentRepository(db_session)
        created = await _create_document(repo, test_user)
        await db_session.commit()

        other_user_id = uuid.uuid4()
        result = await repo.get_by_id(created.id, user_id=other_user_id)

        assert result is None

    async def test_list_for_user_filters_by_status_and_paginates(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        repo = DocumentRepository(db_session)
        doc1 = await _create_document(repo, test_user, filename="a.pdf")
        doc2 = await _create_document(repo, test_user, filename="b.pdf")
        await repo.update_status(doc1.id, user_id=test_user.id, status=DocumentStatus.COMPLETED)
        await db_session.commit()

        completed_items, completed_total = await repo.list_for_user(
            user_id=test_user.id, status=DocumentStatus.COMPLETED, limit=20, offset=0
        )
        all_items, all_total = await repo.list_for_user(
            user_id=test_user.id, status=None, limit=20, offset=0
        )

        assert completed_total == 1
        assert [item.id for item in completed_items] == [doc1.id]
        assert all_total == 2
        assert {item.id for item in all_items} == {doc1.id, doc2.id}

    async def test_update_status_sets_error_message(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        repo = DocumentRepository(db_session)
        created = await _create_document(repo, test_user)
        await db_session.commit()

        updated = await repo.update_status(
            created.id, user_id=test_user.id, status=DocumentStatus.FAILED, error_message="boom"
        )
        await db_session.commit()

        assert updated is not None
        assert updated.status == DocumentStatus.FAILED
        assert updated.error_message == "boom"

    async def test_delete_removes_document(self, db_session: AsyncSession, test_user: User) -> None:
        repo = DocumentRepository(db_session)
        created = await _create_document(repo, test_user)
        await db_session.commit()

        deleted = await repo.delete(created.id, user_id=test_user.id)
        await db_session.commit()

        assert deleted is True
        assert await repo.get_by_id(created.id, user_id=test_user.id) is None

    async def test_delete_nonexistent_returns_false(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        repo = DocumentRepository(db_session)
        assert await repo.delete(uuid.uuid4(), user_id=test_user.id) is False

    async def test_delete_document_cascades_to_chunks(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        document_repo = DocumentRepository(db_session)
        chunk_repo = ChunkRepository(db_session)
        document = await _create_document(document_repo, test_user)
        await chunk_repo.replace_all_for_document(
            document.id,
            [ChunkData(chunk_index=0, content="hello", token_count=1, metadata={})],
        )
        await db_session.commit()

        await document_repo.delete(document.id, user_id=test_user.id)
        await db_session.commit()

        remaining_chunks = await chunk_repo.list_for_document(document.id)
        assert remaining_chunks == []


class TestChunkRepository:
    async def test_replace_all_for_document_is_idempotent(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        document_repo = DocumentRepository(db_session)
        chunk_repo = ChunkRepository(db_session)
        document = await _create_document(document_repo, test_user)
        await db_session.commit()

        await chunk_repo.replace_all_for_document(
            document.id,
            [ChunkData(chunk_index=0, content="first version", token_count=2, metadata={})],
        )
        await db_session.commit()

        await chunk_repo.replace_all_for_document(
            document.id,
            [
                ChunkData(chunk_index=0, content="second version a", token_count=3, metadata={}),
                ChunkData(chunk_index=1, content="second version b", token_count=3, metadata={}),
            ],
        )
        await db_session.commit()

        chunks = await chunk_repo.list_for_document(document.id)
        assert [chunk.content for chunk in chunks] == ["second version a", "second version b"]

    async def test_unique_constraint_on_document_id_and_chunk_index(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        document_repo = DocumentRepository(db_session)
        document = await _create_document(document_repo, test_user)
        await db_session.commit()

        db_session.add(
            DocumentChunk(document_id=document.id, chunk_index=0, content="a", token_count=1)
        )
        await db_session.commit()

        db_session.add(
            DocumentChunk(
                document_id=document.id, chunk_index=0, content="duplicate", token_count=1
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()
