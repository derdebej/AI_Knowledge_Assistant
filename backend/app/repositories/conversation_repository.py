"""See specs/ARCHITECTURE.md §2.6 and specs/DATABASE.md §3.4-3.5.

Every method is scoped by `user_id` - this is the enforcement point for data
isolation (specs/DATABASE.md §9), not just a UI-level filter.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation
from app.models.document import Document


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, user_id: uuid.UUID, documents: list[Document]) -> Conversation:
        conversation = Conversation(user_id=user_id, documents=documents)
        self._session.add(conversation)
        await self._session.flush()
        return conversation

    async def get_by_id(
        self, conversation_id: uuid.UUID, *, user_id: uuid.UUID
    ) -> Conversation | None:
        stmt = (
            select(Conversation)
            .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .options(selectinload(Conversation.documents))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self, *, user_id: uuid.UUID, limit: int = 20, offset: int = 0
    ) -> tuple[list[Conversation], int]:
        count_stmt = (
            select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)
        )
        total = (await self._session.execute(count_stmt)).scalar_one()

        list_stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items = list((await self._session.execute(list_stmt)).scalars().all())
        return items, total
