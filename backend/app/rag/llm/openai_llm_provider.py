"""OpenAI chat-completion adapter. Implements the `LLMProvider` port.

See specs/RAG_PIPELINE.md §2.7. The port takes a single fully-assembled
prompt string (see `app.rag.prompting.prompt_builder`) - this adapter's only
job is to send it to the Chat Completions API and hand back generated text,
not to interpret or restructure the prompt.
"""

from collections.abc import AsyncIterator

from openai import AsyncOpenAI


class OpenAILLMProvider:
    """Implements the `LLMProvider` port."""

    def __init__(self, *, client: AsyncOpenAI, model: str, temperature: float) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature

    async def generate(self, prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        response_stream = await self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        async for chunk in response_stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
