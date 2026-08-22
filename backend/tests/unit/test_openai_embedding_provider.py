"""Batching contract for the OpenAI embedding adapter, against a fake client
- no real network access. See specs/TESTING.md §2.
"""

from dataclasses import dataclass

from app.rag.embeddings.openai_embedding_provider import OpenAIEmbeddingProvider


@dataclass
class _FakeEmbeddingItem:
    embedding: list[float]
    index: int


@dataclass
class _FakeEmbeddingResponse:
    data: list[_FakeEmbeddingItem]


class _FakeEmbeddingsResource:
    def __init__(self, *, reverse_response_order: bool = False) -> None:
        self.calls: list[list[str]] = []
        self._reverse_response_order = reverse_response_order

    async def create(self, *, model: str, input: list[str]) -> _FakeEmbeddingResponse:
        self.calls.append(list(input))
        items = [
            _FakeEmbeddingItem(embedding=[float(len(text)), float(index)], index=index)
            for index, text in enumerate(input)
        ]
        if self._reverse_response_order:
            items.reverse()
        return _FakeEmbeddingResponse(data=items)


class _FakeOpenAIClient:
    def __init__(self, *, reverse_response_order: bool = False) -> None:
        self.embeddings = _FakeEmbeddingsResource(reverse_response_order=reverse_response_order)


class TestOpenAIEmbeddingProvider:
    async def test_empty_input_returns_no_embeddings_and_makes_no_call(self) -> None:
        client = _FakeOpenAIClient()
        provider = OpenAIEmbeddingProvider(client=client, model="text-embedding-3-small")

        result = await provider.embed([])

        assert result == []
        assert client.embeddings.calls == []

    async def test_small_input_makes_a_single_batched_call(self) -> None:
        client = _FakeOpenAIClient()
        provider = OpenAIEmbeddingProvider(
            client=client, model="text-embedding-3-small", batch_size=10
        )

        result = await provider.embed(["a", "bb", "ccc"])

        assert len(result) == 3
        assert client.embeddings.calls == [["a", "bb", "ccc"]]

    async def test_input_exceeding_batch_size_splits_into_multiple_calls(self) -> None:
        client = _FakeOpenAIClient()
        provider = OpenAIEmbeddingProvider(
            client=client, model="text-embedding-3-small", batch_size=2
        )

        result = await provider.embed(["a", "b", "c", "d", "e"])

        assert len(result) == 5
        assert client.embeddings.calls == [["a", "b"], ["c", "d"], ["e"]]

    async def test_embeddings_returned_in_input_order_even_if_response_is_reordered(self) -> None:
        client = _FakeOpenAIClient(reverse_response_order=True)
        provider = OpenAIEmbeddingProvider(
            client=client, model="text-embedding-3-small", batch_size=10
        )

        result = await provider.embed(["one", "two", "three"])

        # The fake encodes (text length, position) into each embedding -
        # asserting against that proves ordering survived a shuffled response.
        assert result == [[3.0, 0.0], [3.0, 1.0], [5.0, 2.0]]
