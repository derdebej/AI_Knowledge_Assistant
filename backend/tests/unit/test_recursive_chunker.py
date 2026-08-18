from app.rag.chunking.recursive_chunker import RecursiveCharacterChunker


class TestRecursiveCharacterChunker:
    def test_empty_input_returns_no_chunks(self) -> None:
        chunker = RecursiveCharacterChunker(chunk_size=50, chunk_overlap=10)
        assert chunker.split("") == []

    def test_whitespace_only_input_returns_no_chunks(self) -> None:
        chunker = RecursiveCharacterChunker(chunk_size=50, chunk_overlap=10)
        assert chunker.split("   \n\n  ") == []

    def test_single_paragraph_under_chunk_size_returns_one_chunk(self) -> None:
        chunker = RecursiveCharacterChunker(chunk_size=1000, chunk_overlap=150)
        text = "A short paragraph well under the chunk size limit."
        chunks = chunker.split(text)
        assert len(chunks) == 1
        assert chunks[0].content == text
        assert chunks[0].chunk_index == 0

    def test_long_text_splits_into_expected_chunk_count(self) -> None:
        chunker = RecursiveCharacterChunker(chunk_size=50, chunk_overlap=10)
        text = (
            "This is paragraph one. It has some words.\n\n"
            "This is paragraph two, which is a bit longer and should split."
        )
        chunks = chunker.split(text)
        assert len(chunks) == 3
        assert chunks[0].content == "This is paragraph one. It has some words."

    def test_chunk_index_is_sequential_and_ordered(self) -> None:
        chunker = RecursiveCharacterChunker(chunk_size=50, chunk_overlap=10)
        text = (
            "This is paragraph one. It has some words.\n\n"
            "This is paragraph two, which is a bit longer and should split."
        )
        chunks = chunker.split(text)
        assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))

    def test_overlap_is_present_at_chunk_boundary(self) -> None:
        chunker = RecursiveCharacterChunker(chunk_size=50, chunk_overlap=10)
        text = (
            "This is paragraph one. It has some words.\n\n"
            "This is paragraph two, which is a bit longer and should split."
        )
        chunks = chunker.split(text)
        # The word "and" straddles the boundary between the 2nd and 3rd chunk -
        # chunk_overlap keeps it present at the end of one and the start of the next.
        assert chunks[1].content.endswith("and")
        assert chunks[2].content.startswith("and")

    def test_token_count_is_positive_for_every_chunk(self) -> None:
        chunker = RecursiveCharacterChunker(chunk_size=50, chunk_overlap=10)
        text = (
            "This is paragraph one. It has some words.\n\n"
            "This is paragraph two, which is a bit longer and should split."
        )
        for chunk in chunker.split(text):
            assert chunk.token_count >= 1

    def test_base_metadata_is_copied_into_every_chunk(self) -> None:
        chunker = RecursiveCharacterChunker(chunk_size=1000, chunk_overlap=150)
        base_metadata = {"original_filename": "report.pdf", "page_number": 4}
        chunks = chunker.split("Some short content.", base_metadata=base_metadata)
        assert len(chunks) == 1
        assert chunks[0].metadata == base_metadata
        assert chunks[0].metadata is not base_metadata

    def test_no_base_metadata_yields_empty_dict(self) -> None:
        chunker = RecursiveCharacterChunker(chunk_size=1000, chunk_overlap=150)
        chunks = chunker.split("Some short content.")
        assert chunks[0].metadata == {}
