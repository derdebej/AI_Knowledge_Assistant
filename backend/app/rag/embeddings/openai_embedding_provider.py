"""OpenAI embedding adapter. Implements the `EmbeddingProvider` port.

See specs/RAG_PIPELINE.md §1.6 and §2.2 - query and document embeddings
must come from this same model/adapter to be comparable.
"""

from openai import AsyncOpenAI

# OpenAI's embeddings endpoint accepts up to 2048 inputs per request; batching
# well under that keeps a single request's payload/latency bounded and limits
# the blast radius of one failed batch on a large document's chunk list.
_DEFAULT_BATCH_SIZE = 100


class OpenAIEmbeddingProvider:
    """Implements the `EmbeddingProvider` port."""

    def __init__(
        self, *, client: AsyncOpenAI, model: str, batch_size: int = _DEFAULT_BATCH_SIZE
    ) -> None:
        self._client = client
        self._model = model
        self._batch_size = batch_size

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            response = await self._client.embeddings.create(model=self._model, input=batch)
            # The API is documented to preserve input order, but sorting by
            # the returned `index` is a cheap guard against relying on that
            # implicitly - a mismatch here would silently corrupt every
            # chunk's embedding-to-content mapping.
            ordered = sorted(response.data, key=lambda item: item.index)
            embeddings.extend(item.embedding for item in ordered)
        return embeddings
