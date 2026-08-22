"""Top-K + relevance-threshold + scoping logic, against `FakeVectorStore`.
See specs/TESTING.md §2 and specs/RAG_PIPELINE.md §2.3.
"""

import uuid

from app.services.retrieval_service import RetrievalService
from tests.fakes import FakeVectorStore


class _FixedEmbeddingProvider:
    """Always returns the same query vector - lets tests pin exact cosine
    similarity scores for seeded chunks instead of depending on a hash."""

    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector for _ in texts]


_QUERY_VECTOR = [1.0, 0.0]


def _make_service(
    vector_store: FakeVectorStore, *, top_k: int = 5, relevance_threshold: float = 0.75
) -> RetrievalService:
    return RetrievalService(
        embedding_provider=_FixedEmbeddingProvider(_QUERY_VECTOR),
        vector_store=vector_store,
        top_k=top_k,
        relevance_threshold=relevance_threshold,
    )


class TestRetrievalServiceThreshold:
    async def test_filters_out_chunks_below_the_relevance_threshold(self) -> None:
        user_id = uuid.uuid4()
        store = FakeVectorStore()
        store.seed(
            document_id="doc-1", user_id=str(user_id), content="on topic", embedding=[1.0, 0.0]
        )  # similarity 1.0
        store.seed(
            document_id="doc-1", user_id=str(user_id), content="off topic", embedding=[0.6, 0.8]
        )  # similarity 0.6

        results = await _make_service(store).retrieve("question", user_id=user_id)

        assert [chunk.content for chunk in results] == ["on topic"]

    async def test_chunk_exactly_at_threshold_is_included(self) -> None:
        user_id = uuid.uuid4()
        store = FakeVectorStore()
        store.seed(
            document_id="doc-1",
            user_id=str(user_id),
            content="borderline",
            embedding=[0.75, (1 - 0.75**2) ** 0.5],
        )  # similarity == 0.75

        results = await _make_service(store, relevance_threshold=0.75).retrieve(
            "question", user_id=user_id
        )

        assert [chunk.content for chunk in results] == ["borderline"]

    async def test_no_chunks_above_threshold_returns_empty_list(self) -> None:
        user_id = uuid.uuid4()
        store = FakeVectorStore()
        store.seed(
            document_id="doc-1", user_id=str(user_id), content="unrelated", embedding=[0.0, 1.0]
        )  # similarity 0.0

        results = await _make_service(store).retrieve("question", user_id=user_id)

        assert results == []


class TestRetrievalServiceTopK:
    async def test_respects_top_k_even_when_more_chunks_clear_the_threshold(self) -> None:
        user_id = uuid.uuid4()
        store = FakeVectorStore()
        for i in range(5):
            store.seed(
                document_id="doc-1",
                user_id=str(user_id),
                content=f"chunk-{i}",
                embedding=[1.0, 0.0],
            )

        results = await _make_service(store, top_k=2).retrieve("question", user_id=user_id)

        assert len(results) == 2


class TestRetrievalServiceScoping:
    async def test_only_returns_chunks_for_the_requesting_user(self) -> None:
        user_id = uuid.uuid4()
        other_user_id = uuid.uuid4()
        store = FakeVectorStore()
        store.seed(document_id="doc-1", user_id=str(user_id), content="mine", embedding=[1.0, 0.0])
        store.seed(
            document_id="doc-2",
            user_id=str(other_user_id),
            content="not mine",
            embedding=[1.0, 0.0],
        )

        results = await _make_service(store).retrieve("question", user_id=user_id)

        assert [chunk.content for chunk in results] == ["mine"]

    async def test_document_ids_filter_narrows_results(self) -> None:
        user_id = uuid.uuid4()
        in_scope_document_id = uuid.uuid4()
        out_of_scope_document_id = uuid.uuid4()
        store = FakeVectorStore()
        store.seed(
            document_id=str(in_scope_document_id),
            user_id=str(user_id),
            content="in scope",
            embedding=[1.0, 0.0],
        )
        store.seed(
            document_id=str(out_of_scope_document_id),
            user_id=str(user_id),
            content="out of scope",
            embedding=[1.0, 0.0],
        )

        results = await _make_service(store).retrieve(
            "question", user_id=user_id, document_ids=[in_scope_document_id]
        )

        assert [chunk.content for chunk in results] == ["in scope"]
