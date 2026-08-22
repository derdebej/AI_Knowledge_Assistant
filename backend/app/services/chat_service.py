"""Turns retrieved chunks into a grounded, cited answer. See
specs/RAG_PIPELINE.md §2.6-2.8 and §5.

Deliberately independent of the API/streaming layer (specs/ROADMAP.md Phase
4): `ask()` is the non-streaming contract used here and by tests; a
streaming caller (Phase 5's SSE endpoint) builds the same prompt via
`build_prompt` and drives `LLMProvider.stream()` directly, since the port's
`generate`/`stream` split means this service can't offer both from one call.
"""

import uuid

from app.domain.entities import ChatAnswer, Citation, RetrievedChunk
from app.domain.ports import LLMProvider
from app.rag.prompting.prompt_builder import NOT_FOUND_MESSAGE, build_prompt
from app.services.retrieval_service import RetrievalService


class ChatService:
    def __init__(self, *, retrieval_service: RetrievalService, llm_provider: LLMProvider) -> None:
        self._retrieval_service = retrieval_service
        self._llm_provider = llm_provider

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


def _build_citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    return [
        Citation(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            similarity_score=chunk.similarity_score,
            rank=rank,
        )
        for rank, chunk in enumerate(chunks, start=1)
    ]
