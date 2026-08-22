"""ChatService against a real Postgres+pgvector database: seed known
chunks/embeddings via the real ingestion pipeline (faked embedding provider),
then verify retrieval + prompt assembly + citations all flow correctly
end-to-end with only the LLM faked. See specs/TESTING.md §3 and
specs/ROADMAP.md Phase 4.
"""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.user import User
from app.rag.prompting.prompt_builder import NOT_FOUND_MESSAGE
from app.rag.vector_store.pgvector_store import PgVectorStore
from app.services.chat_service import ChatService
from app.services.retrieval_service import RetrievalService
from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider

_KNOWN_CONTENT = b"The mitochondria is the powerhouse of the cell."


def _make_chat_service(db_session: AsyncSession, llm_provider: FakeLLMProvider) -> ChatService:
    settings = get_settings()
    return ChatService(
        retrieval_service=RetrievalService(
            embedding_provider=FakeEmbeddingProvider(),
            vector_store=PgVectorStore(db_session),
            top_k=settings.retrieval_top_k,
            relevance_threshold=settings.relevance_threshold,
        ),
        llm_provider=llm_provider,
    )


class TestChatServiceIntegration:
    async def test_answer_references_the_seeded_chunk_and_prompt_contains_its_content(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        upload = await client.post(
            "/api/v1/documents", files={"file": ("notes.txt", _KNOWN_CONTENT, "text/plain")}
        )
        document_id = upload.json()["id"]
        llm_provider = FakeLLMProvider(response="It's the powerhouse of the cell.")

        answer = await _make_chat_service(db_session, llm_provider).ask(
            _KNOWN_CONTENT.decode(), user_id=test_user.id
        )

        assert answer.content == "It's the powerhouse of the cell."
        assert len(answer.citations) == 1
        assert answer.citations[0].document_id == document_id
        assert answer.citations[0].rank == 1
        assert answer.citations[0].similarity_score >= get_settings().relevance_threshold

        assert len(llm_provider.received_prompts) == 1
        prompt = llm_provider.received_prompts[0]
        assert _KNOWN_CONTENT.decode() in prompt
        assert "CONTEXT:" in prompt
        assert "notes.txt" in prompt

    async def test_question_out_of_scope_short_circuits_to_not_found_without_calling_llm(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        await client.post(
            "/api/v1/documents", files={"file": ("notes.txt", _KNOWN_CONTENT, "text/plain")}
        )
        llm_provider = FakeLLMProvider(raise_if_called=True)

        # Scoped to a document with no chunks at all, guaranteeing zero
        # candidates independent of embedding similarity - the reliable way
        # to force the empty-retrieval path against a real pgvector query
        # (specs/RAG_PIPELINE.md §5.1), rather than depending on the fake
        # hash-based embedding happening to score low for some question text.
        answer = await _make_chat_service(db_session, llm_provider).ask(
            _KNOWN_CONTENT.decode(),
            user_id=test_user.id,
            document_ids=[uuid.uuid4()],
        )

        assert answer.content == NOT_FOUND_MESSAGE
        assert answer.citations == []
