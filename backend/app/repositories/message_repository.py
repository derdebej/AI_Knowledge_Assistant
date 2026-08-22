"""See specs/ARCHITECTURE.md §2.6 and specs/DATABASE.md §3.6-3.7."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities import Citation
from app.models.message import Message, MessageCitation


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, conversation_id: uuid.UUID, *, role: str, content: str) -> Message:
        message = Message(conversation_id=conversation_id, role=role, content=content)
        self._session.add(message)
        await self._session.flush()
        return message

    async def add_citations(self, message_id: uuid.UUID, citations: list[Citation]) -> None:
        rows = [
            MessageCitation(
                message_id=message_id,
                chunk_id=uuid.UUID(citation.chunk_id),
                similarity_score=citation.similarity_score,
                rank=citation.rank,
            )
            for citation in citations
        ]
        self._session.add_all(rows)
        await self._session.flush()

    async def list_for_conversation(
        self, conversation_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[Message], int]:
        count_stmt = (
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation_id)
        )
        total = (await self._session.execute(count_stmt)).scalar_one()

        list_stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
            .offset(offset)
            .options(selectinload(Message.citations).selectinload(MessageCitation.chunk))
        )
        items = list((await self._session.execute(list_stmt)).scalars().all())
        return items, total
