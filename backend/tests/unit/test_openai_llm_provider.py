"""Contract of the OpenAI chat-completion adapter, against a fake client -
no real network access. See specs/TESTING.md §2.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.rag.llm.openai_llm_provider import OpenAILLMProvider


@dataclass
class _FakeMessage:
    content: str | None


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeCompletion:
    choices: list[_FakeChoice]


@dataclass
class _FakeDelta:
    content: str | None


@dataclass
class _FakeStreamChoice:
    delta: _FakeDelta


@dataclass
class _FakeStreamChunk:
    choices: list[_FakeStreamChoice]


class _FakeStream:
    def __init__(self, deltas: list[str | None]) -> None:
        self._deltas = deltas

    def __aiter__(self) -> AsyncIterator[_FakeStreamChunk]:
        return self._generate()

    async def _generate(self) -> AsyncIterator[_FakeStreamChunk]:
        for delta in self._deltas:
            yield _FakeStreamChunk(choices=[_FakeStreamChoice(delta=_FakeDelta(content=delta))])


class _FakeCompletionsResource:
    def __init__(
        self, *, content: str | None = "an answer", stream_deltas: list[str | None] | None = None
    ) -> None:
        self.calls: list[dict[str, object]] = []
        self._content = content
        self._stream_deltas = stream_deltas or ["Hello", ", ", "world", "."]

    async def create(self, **kwargs: object) -> _FakeCompletion | _FakeStream:
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return _FakeStream(self._stream_deltas)
        return _FakeCompletion(choices=[_FakeChoice(message=_FakeMessage(content=self._content))])


@dataclass
class _FakeChat:
    completions: _FakeCompletionsResource = field(default_factory=_FakeCompletionsResource)


class _FakeOpenAIClient:
    def __init__(self, completions: _FakeCompletionsResource | None = None) -> None:
        self.chat = _FakeChat(completions=completions or _FakeCompletionsResource())


class TestOpenAILLMProviderGenerate:
    async def test_generate_sends_the_prompt_as_a_single_message_and_returns_its_content(
        self,
    ) -> None:
        completions = _FakeCompletionsResource(content="The answer is 42.")
        client = _FakeOpenAIClient(completions)
        provider = OpenAILLMProvider(client=client, model="gpt-4o-mini", temperature=0.2)

        result = await provider.generate("assembled prompt text")

        assert result == "The answer is 42."
        assert completions.calls == [
            {
                "model": "gpt-4o-mini",
                "temperature": 0.2,
                "messages": [{"role": "user", "content": "assembled prompt text"}],
            }
        ]

    async def test_generate_returns_empty_string_when_content_is_none(self) -> None:
        client = _FakeOpenAIClient(_FakeCompletionsResource(content=None))
        provider = OpenAILLMProvider(client=client, model="gpt-4o-mini", temperature=0.2)

        result = await provider.generate("prompt")

        assert result == ""


class TestOpenAILLMProviderStream:
    async def test_stream_yields_each_non_empty_delta_in_order(self) -> None:
        completions = _FakeCompletionsResource(stream_deltas=["Hel", "lo", None, "!"])
        client = _FakeOpenAIClient(completions)
        provider = OpenAILLMProvider(client=client, model="gpt-4o-mini", temperature=0.2)

        chunks = [chunk async for chunk in provider.stream("prompt")]

        assert chunks == ["Hel", "lo", "!"]
        assert completions.calls[0]["stream"] is True
