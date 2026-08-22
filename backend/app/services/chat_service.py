"""Turns retrieved chunks into a grounded, cited answer, and owns the
conversation/message use cases built on top of it. See specs/RAG_PIPELINE.md
§2.6-2.8 and §5, specs/ARCHITECTURE.md §5.2, and specs/API.md §3.

`ask()` is the non-streaming contract from Phase 4 - kept as-is (no
persistence, no API/streaming dependency) for tests and any future
non-streaming caller (e.g. the Phase 8 eval harness). `stream_answer()` is
Phase 5's addition: it persists the user/assistant messages and citations
and yields `ChatStreamEvent`s for the API layer to format as SSE - the one
piece it deliberately does NOT do is decide HTTP status codes or wire
formatting, which stays the API layer's job (specs/ARCHITECTURE.md §2.1).
"""

import uuid
from collections.abc import AsyncIterator

from app.domain.entities import ChatAnswer, ChatStreamEvent, Citation, RetrievedChunk
from app.domain.exceptions import DocumentOwnershipError
from app.domain.ports import LLMProvider
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole
from app.rag.prompting.prompt_builder import NOT_FOUND_MESSAGE, build_prompt
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.message_repository import MessageRepository
from app.services.retrieval_service import RetrievalService


class ChatService:
    def __init__(
        self,
        *,
        retrieval_service: RetrievalService,
        llm_provider: LLMProvider,
        document_repository: DocumentRepository,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._llm_provider = llm_provider
        self._document_repository = document_repository
        self._conversation_repository = conversation_repository
        self._message_repository = message_repository

    async def ask(
        self, question: str, *, user_id: uuid.UUID, document_ids: list[uuid.UUID] | None = None
    ) -> ChatAnswer:
        chunks = await self._retrieval_service.retrieve(
            question, user_id=user_id, document_ids=document_ids
        )
        if not chunks:
            # Retrieval-level short-circuit (specs/RAG_PIPELINE.md §5.1): zero
            # chunks cleared the relevance threshold, so no LLM call is made
            # at all - deterministic, zero-cost, zero-hallucination-risk.
            return ChatAnswer(content=NOT_FOUND_MESSAGE, citations=[])

        prompt = build_prompt(question, chunks)
        answer = await self._llm_provider.generate(prompt)
        return ChatAnswer(content=answer, citations=_build_citations(chunks))

    async def create_conversation(
        self, *, user_id: uuid.UUID, document_ids: list[uuid.UUID] | None
    ) -> Conversation:
        documents = []
        if document_ids:
            documents = await self._document_repository.get_by_ids(document_ids, user_id=user_id)
            # Every requested ID must resolve to a document owned by this
            # user - specs/API.md §3 ("All IDs must belong to the requesting
            # user (400 otherwise)"), enforced here rather than in the
            # repository since "ownership" is a business rule, not a query
            # detail (specs/ARCHITECTURE.md §2.3).
            if len(documents) != len(set(document_ids)):
                raise DocumentOwnershipError(
                    "One or more documents do not belong to the requesting user"
                )
        return await self._conversation_repository.create(user_id=user_id, documents=documents)

    async def get_conversation(
        self, conversation_id: uuid.UUID, *, user_id: uuid.UUID
    ) -> Conversation | None:
        return await self._conversation_repository.get_by_id(conversation_id, user_id=user_id)

    async def list_conversations(
        self, *, user_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[list[Conversation], int]:
        return await self._conversation_repository.list_for_user(
            user_id=user_id, limit=limit, offset=offset
        )

    async def list_messages(
        self, conversation_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[Message], int]:
        """Ownership is the caller's responsibility (via `get_conversation`
        first) - this assumes `conversation_id` has already been resolved as
        belonging to the requesting user."""
        return await self._message_repository.list_for_conversation(
            conversation_id, limit=limit, offset=offset
        )

    async def stream_answer(
        self, *, conversation: Conversation, question: str, user_id: uuid.UUID
    ) -> AsyncIterator[ChatStreamEvent]:
        """Persists the user message, retrieves + generates the answer, and
        yields SSE-shaped events in the order specs/API.md §3 documents:
        `token`* -> `citations` -> `done` (or a single `token` + empty
        `citations` + `done` on the not-found short-circuit). Assumes
        `conversation` was already resolved/ownership-checked by the caller
        (mirrors `list_messages` - see specs/API.md §3's pre-stream
        validation requirement, which needs the check to happen before any
        `StreamingResponse` is constructed, not inside this generator).
        """
        document_ids = [document.id for document in conversation.documents] or None
        await self._message_repository.create(
            conversation.id, role=MessageRole.USER, content=question
        )

        chunks = await self._retrieval_service.retrieve(
            question, user_id=user_id, document_ids=document_ids
        )
        if not chunks:
            message = await self._message_repository.create(
                conversation.id, role=MessageRole.ASSISTANT, content=NOT_FOUND_MESSAGE
            )
            yield ChatStreamEvent("token", {"content": NOT_FOUND_MESSAGE})
            yield ChatStreamEvent("citations", {"citations": []})
            yield ChatStreamEvent("done", {"message_id": str(message.id)})
            return

        prompt = build_prompt(question, chunks)
        answer_parts: list[str] = []
        async for delta in self._llm_provider.stream(prompt):
            answer_parts.append(delta)
            yield ChatStreamEvent("token", {"content": delta})

        citations = _build_citations(chunks)
        message = await self._message_repository.create(
            conversation.id, role=MessageRole.ASSISTANT, content="".join(answer_parts)
        )
        await self._message_repository.add_citations(message.id, citations)

        yield ChatStreamEvent("citations", {"citations": [_citation_payload(c) for c in citations]})
        yield ChatStreamEvent("done", {"message_id": str(message.id)})


def _build_citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    return [
        Citation(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            document_name=str(chunk.metadata.get("original_filename", "document")),
            page_number=chunk.metadata.get("page_number"),
            similarity_score=chunk.similarity_score,
            rank=rank,
        )
        for rank, chunk in enumerate(chunks, start=1)
    ]


def _citation_payload(citation: Citation) -> dict[str, object]:
    return {
        "document_id": citation.document_id,
        "document_name": citation.document_name,
        "page_number": citation.page_number,
        "chunk_id": citation.chunk_id,
        "similarity_score": citation.similarity_score,
        "rank": citation.rank,
    }
