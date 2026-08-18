"""Chunker adapter wrapping LangChain's RecursiveCharacterTextSplitter.

This is the one place LangChain is used - a well-tested utility, not a
framework the app is built around. See specs/ARCHITECTURE.md §2.5 and
specs/RAG_PIPELINE.md §1.5 for the parameter rationale.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.domain.entities import ChunkData

# Paragraph -> line -> sentence -> word -> character, so splits land on the
# most semantically meaningful boundary available (specs/RAG_PIPELINE.md §1.5).
_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

# Rough, tokenizer-free proxy (~4 chars/token for English prose) used only for
# the stored `token_count` metadata field - not for splitting decisions, which
# are character-based per specs/RAG_PIPELINE.md §1.5.
_CHARS_PER_TOKEN_ESTIMATE = 4


class RecursiveCharacterChunker:
    """Implements the `Chunker` port."""

    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=_SEPARATORS,
        )

    def split(
        self, text: str, *, base_metadata: dict[str, object] | None = None
    ) -> list[ChunkData]:
        if not text.strip():
            return []

        raw_chunks = self._splitter.split_text(text)
        return [
            ChunkData(
                chunk_index=index,
                content=chunk,
                token_count=max(1, len(chunk) // _CHARS_PER_TOKEN_ESTIMATE),
                metadata=dict(base_metadata or {}),
            )
            for index, chunk in enumerate(raw_chunks)
        ]
