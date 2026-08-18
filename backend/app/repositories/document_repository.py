"""See specs/ARCHITECTURE.md §2.6.

Every method is scoped by `user_id` - this is the enforcement point for data
isolation (specs/DATABASE.md §9), not just a UI-level filter.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        """Commits early, ahead of the request's own end-of-request commit.

        Needed specifically before scheduling a `BackgroundTasks` callback:
        FastAPI runs background tasks *before* a `yield`-dependency's
        post-yield cleanup (where the request session would otherwise
        commit), so without this the background task's own fresh session
        can't yet see the row just written - see specs/ARCHITECTURE.md §7.
        """
        await self._session.commit()

    async def create(
        self,
        *,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        filename: str,
        original_filename: str,
        content_type: str,
        file_size_bytes: int,
        storage_path: str,
    ) -> Document:
        document = Document(
            id=document_id,
            user_id=user_id,
            filename=filename,
            original_filename=original_filename,
            content_type=content_type,
            file_size_bytes=file_size_bytes,
            storage_path=storage_path,
        )
        self._session.add(document)
        await self._session.flush()
        return document

    async def get_by_id(self, document_id: uuid.UUID, *, user_id: uuid.UUID) -> Document | None:
        stmt = select(Document).where(Document.id == document_id, Document.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        *,
        user_id: uuid.UUID,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        filters = [Document.user_id == user_id]
        if status is not None:
            filters.append(Document.status == status)

        count_stmt = select(func.count()).select_from(Document).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        list_stmt = (
            select(Document)
            .where(*filters)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items = list((await self._session.execute(list_stmt)).scalars().all())
        return items, total

    async def update_status(
        self,
        document_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        status: str,
        error_message: str | None = None,
        page_count: int | None = None,
    ) -> Document | None:
        document = await self.get_by_id(document_id, user_id=user_id)
        if document is None:
            return None
        document.status = status
        document.error_message = error_message
        if page_count is not None:
            document.page_count = page_count
        await self._session.flush()
        return document

    async def delete(self, document_id: uuid.UUID, *, user_id: uuid.UUID) -> bool:
        document = await self.get_by_id(document_id, user_id=user_id)
        if document is None:
            return False
        await self._session.delete(document)
        await self._session.flush()
        return True
