"""Conversations, messages, and SSE streaming. See specs/API.md §3.

Routers translate domain exceptions to HTTP responses and, for the
streaming endpoint, to SSE `error` frames - they never construct
`StreamingResponse` until *after* conversation ownership has been checked
(specs/API.md §3's "pre-stream validation" requirement: once
`StreamingResponse` exists, the `200` status is already committed, so a
`ConversationNotFoundError` raised inside the generator could no longer
become a clean `404`).
"""

import json
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse

from app.core.deps import CurrentUserIdDep
from app.core.di import get_chat_service
from app.core.logging import get_logger
from app.domain.entities import ChatStreamEvent
from app.domain.exceptions import ConversationNotFoundError
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationListItem,
    ConversationListResponse,
    ConversationResponse,
)
from app.schemas.message import (
    CitationResponse,
    MessageCreateRequest,
    MessageListResponse,
    MessageResponse,
)
from app.services.chat_service import ChatService

logger = get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["chat"])

ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


def _to_conversation_response(conversation: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        document_ids=[document.id for document in conversation.documents],
        created_at=conversation.created_at,
    )


def _to_conversation_detail(conversation: Conversation) -> ConversationDetailResponse:
    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        document_ids=[document.id for document in conversation.documents],
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _to_message_response(message: Message) -> MessageResponse:
    citations = None
    if message.role == MessageRole.ASSISTANT:
        citations = [
            CitationResponse(
                document_id=citation.chunk.document_id,
                document_name=citation.chunk.chunk_metadata.get("original_filename", "document"),
                page_number=citation.chunk.chunk_metadata.get("page_number"),
                chunk_id=citation.chunk_id,
                similarity_score=citation.similarity_score,
                rank=citation.rank,
            )
            for citation in message.citations
        ]
    return MessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        citations=citations,
    )


def _format_sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ConversationResponse)
async def create_conversation(
    payload: ConversationCreateRequest, chat_service: ChatServiceDep, user_id: CurrentUserIdDep
) -> ConversationResponse:
    conversation = await chat_service.create_conversation(
        user_id=user_id, document_ids=payload.document_ids or None
    )
    return _to_conversation_response(conversation)


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    chat_service: ChatServiceDep,
    user_id: CurrentUserIdDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ConversationListResponse:
    items, total = await chat_service.list_conversations(
        user_id=user_id, limit=limit, offset=offset
    )
    return ConversationListResponse(
        items=[ConversationListItem.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID, chat_service: ChatServiceDep, user_id: CurrentUserIdDep
) -> ConversationDetailResponse:
    conversation = await chat_service.get_conversation(conversation_id, user_id=user_id)
    if conversation is None:
        raise ConversationNotFoundError("Conversation not found")
    return _to_conversation_detail(conversation)


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def list_messages(
    conversation_id: uuid.UUID,
    chat_service: ChatServiceDep,
    user_id: CurrentUserIdDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MessageListResponse:
    conversation = await chat_service.get_conversation(conversation_id, user_id=user_id)
    if conversation is None:
        raise ConversationNotFoundError("Conversation not found")

    messages, total = await chat_service.list_messages(conversation_id, limit=limit, offset=offset)
    return MessageListResponse(
        items=[_to_message_response(message) for message in messages], total=total
    )


@router.post("/{conversation_id}/messages")
async def post_message(
    conversation_id: uuid.UUID,
    payload: MessageCreateRequest,
    chat_service: ChatServiceDep,
    user_id: CurrentUserIdDep,
) -> StreamingResponse:
    # Ownership check happens here, before any StreamingResponse exists - see
    # the module docstring for why this can't move inside the generator.
    conversation = await chat_service.get_conversation(conversation_id, user_id=user_id)
    if conversation is None:
        raise ConversationNotFoundError("Conversation not found")

    async def event_stream() -> AsyncIterator[str]:
        try:
            events: AsyncIterator[ChatStreamEvent] = chat_service.stream_answer(
                conversation=conversation, question=payload.content, user_id=user_id
            )
            async for event in events:
                yield _format_sse(event.event, event.data)
        except Exception as exc:
            # Headers/status are already committed once streaming starts
            # (specs/API.md §3) - a mid-stream failure can only be reported
            # as an `error` SSE frame, never a different HTTP status. Full
            # error logged server-side only, per specs/SECURITY.md.
            logger.error(
                "chat_stream_failed",
                conversation_id=str(conversation_id),
                error_type=type(exc).__name__,
                error=str(exc),
            )
            yield _format_sse(
                "error", {"detail": "An unexpected error occurred while generating the answer."}
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
