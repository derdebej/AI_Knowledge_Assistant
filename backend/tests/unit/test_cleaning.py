from app.documents.cleaning import (
    clean_document_pages,
    clean_page_text,
    strip_repeated_headers_footers,
)


class TestCleanPageText:
    def test_collapses_repeated_whitespace(self) -> None:
        assert clean_page_text("Hello   world") == "Hello world"

    def test_collapses_repeated_blank_lines(self) -> None:
        assert clean_page_text("Para one.\n\n\n\nPara two.") == "Para one.\n\nPara two."

    def test_strips_control_characters(self) -> None:
        assert clean_page_text("Hello\x00\x0bworld") == "Helloworld"

    def test_normalizes_unicode_nfkc(self) -> None:
        # U+FB01 LATIN SMALL LIGATURE FI -> "fi"
        assert clean_page_text("ﬁle") == "file"

    def test_strips_leading_trailing_whitespace(self) -> None:
        assert clean_page_text("  \n  Hello  \n  ") == "Hello"

    def test_removes_trailing_spaces_before_newline(self) -> None:
        assert clean_page_text("line one   \nline two") == "line one\nline two"

    def test_empty_input_yields_empty_output(self) -> None:
        assert clean_page_text("") == ""


class TestStripRepeatedHeadersFooters:
    def test_single_page_only_strips_page_numbers(self) -> None:
        pages = ["Header\nContent\n42"]
        result = strip_repeated_headers_footers(pages)
        assert result == ["Header\nContent"]

    def test_line_repeated_across_majority_of_pages_is_removed(self) -> None:
        pages = [
            "Confidential Report\nPage one content.",
            "Confidential Report\nPage two content.",
            "Confidential Report\nPage three content.",
        ]
        result = strip_repeated_headers_footers(pages)
        for page in result:
            assert "Confidential Report" not in page
        assert "Page one content." in result[0]
        assert "Page two content." in result[1]
        assert "Page three content." in result[2]

    def test_line_appearing_on_minority_of_pages_is_kept(self) -> None:
        pages = [
            "Unique note for page one.\nContent.",
            "Content.",
            "Content.",
        ]
        result = strip_repeated_headers_footers(pages)
        assert "Unique note for page one." in result[0]

    def test_page_number_only_lines_are_removed(self) -> None:
        pages = [
            "Content one.\nPage 1",
            "Content two.\n2 / 10",
            "Content three.\n3",
        ]
        result = strip_repeated_headers_footers(pages)
        assert "1" not in result[0].splitlines()
        assert all("Content" in page for page in result)


class TestCleanDocumentPages:
    def test_full_pipeline_on_multi_page_document(self) -> None:
        pages = [
            "MyDoc Inc.\n\n\nFirst   page   content.\n42",
            "MyDoc Inc.\n\n\nSecond   page   content.\n43",
        ]
        result = clean_document_pages(pages)
        assert len(result) == 2
        for page in result:
            assert "MyDoc Inc." not in page
        assert "First page content." in result[0]
        assert "Second page content." in result[1]

    def test_empty_document_list(self) -> None:
        assert clean_document_pages([]) == []
