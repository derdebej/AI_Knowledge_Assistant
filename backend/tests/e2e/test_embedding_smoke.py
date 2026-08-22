"""Smoke test against the real OpenAI embeddings API. Gated behind
`RUN_E2E_LLM_TESTS=1` (a real `OPENAI_API_KEY` must also be configured) so it
never runs by default - see specs/TESTING.md §4 and specs/ROADMAP.md Phase 3
("using real OpenAI calls in at least one smoke test").
"""

import os

import pytest
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.rag.embeddings.openai_embedding_provider import OpenAIEmbeddingProvider

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E_LLM_TESTS") != "1",
    reason="gated behind RUN_E2E_LLM_TESTS=1 - makes a real OpenAI API call",
)


class TestOpenAIEmbeddingProviderSmoke:
    async def test_embeds_real_text_via_the_openai_api(self) -> None:
        settings = get_settings()
        provider = OpenAIEmbeddingProvider(
            client=AsyncOpenAI(api_key=settings.openai_api_key), model=settings.embedding_model
        )

        embeddings = await provider.embed(
            ["The sky is blue.", "Quantum computers use qubits instead of classical bits."]
        )

        assert len(embeddings) == 2
        assert all(len(vector) == settings.embedding_dimensions for vector in embeddings)
        assert embeddings[0] != embeddings[1]
