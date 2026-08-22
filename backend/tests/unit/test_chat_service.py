"""ChatService orchestration: the "not found" short-circuit never calls the
LLM, and the happy path assembles a prompt from retrieved chunks and returns
citations reflecting exactly what was shown to the model. See
specs/TESTING.md §2 and specs/RAG_PIPELINE.md §5, §2.8.
"""

import uuid

from app.rag.prompting.prompt_builder import NOT_FOUND_MESSAGE
from app.services.chat_service import ChatService
from app.services.retrieval_service import RetrievalService
from tests.fakes import FakeLLMProvider, FakeVectorStore


class _FixedEmbeddingProvider:
    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector for _ in texts]


_QUERY_VECTOR = [1.0, 0.0]


def _make_chat_service(
    vector_store: FakeVectorStore, llm_provider: FakeLLMProvider, *, top_k: int = 5
) -> ChatService:
    retrieval_service = RetrievalService(
        embedding_provider=_FixedEmbeddingProvider(_QUERY_VECTOR),
        vector_store=vector_store,
        top_k=top_k,
        relevance_threshold=0.75,
    )
    return ChatService(retrieval_service=retrieval_service, llm_provider=llm_provider)


class TestChatServiceNotFoundShortCircuit:
    async def test_returns_fixed_refusal_and_never_calls_the_llm_when_no_chunk_clears_threshold(
        self,
    ) -> None:
        user_id = uuid.uuid4()
        store = FakeVectorStore()
        store.seed(
            document_id="doc-1", user_id=str(user_id), content="unrelated", embedding=[0.0, 1.0]
        )  # similarity 0.0, below the 0.75 threshold
        llm_provider = FakeLLMProvider(raise_if_called=True)

        answer = await _make_chat_service(store, llm_provider).ask("question", user_id=user_id)

        assert answer.content == NOT_FOUND_MESSAGE
        assert answer.citations == []

    async def test_returns_fixed_refusal_when_no_chunks_exist_at_all(self) -> None:
        user_id = uuid.uuid4()
        llm_provider = FakeLLMProvider(raise_if_called=True)

        answer = await _make_chat_service(FakeVectorStore(), llm_provider).ask(
            "question", user_id=user_id
        )

        assert answer.content == NOT_FOUND_MESSAGE
        assert answer.citations == []


class TestChatServiceHappyPath:
    async def test_returns_llm_answer_and_includes_retrieved_chunk_content_in_the_prompt(
        self,
    ) -> None:
        user_id = uuid.uuid4()
        store = FakeVectorStore()
        store.seed(
            document_id="doc-1",
            user_id=str(user_id),
            content="the mitochondria is the powerhouse of the cell",
            embedding=[1.0, 0.0],
        )
        llm_provider = FakeLLMProvider(response="It's the powerhouse of the cell.")

        answer = await _make_chat_service(store, llm_provider).ask("question", user_id=user_id)

        assert answer.content == "It's the powerhouse of the cell."
        assert len(llm_provider.received_prompts) == 1
        assert "the mitochondria is the powerhouse of the cell" in llm_provider.received_prompts[0]

    async def test_citations_reflect_rank_document_and_score_of_chunks_shown_to_the_model(
        self,
    ) -> None:
        user_id = uuid.uuid4()
        store = FakeVectorStore()
        store.seed(
            document_id="doc-1",
            user_id=str(user_id),
            content="best match",
            embedding=[1.0, 0.0],
            chunk_id="chunk-best",
        )  # similarity 1.0
        store.seed(
            document_id="doc-2",
            user_id=str(user_id),
            content="second match",
            embedding=[0.8, (1 - 0.8**2) ** 0.5],
            chunk_id="chunk-second",
        )  # similarity 0.8
        llm_provider = FakeLLMProvider()

        answer = await _make_chat_service(store, llm_provider).ask("question", user_id=user_id)

        assert [c.chunk_id for c in answer.citations] == ["chunk-best", "chunk-second"]
        assert [c.rank for c in answer.citations] == [1, 2]
        assert [c.document_id for c in answer.citations] == ["doc-1", "doc-2"]
        assert answer.citations[0].similarity_score > answer.citations[1].similarity_score
