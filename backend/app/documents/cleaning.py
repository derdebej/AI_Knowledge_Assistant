"""Deterministic text cleaning applied before chunking. See specs/RAG_PIPELINE.md §1.3.

Never rewrites content semantically - only removes noise (extraction
artifacts, repeated whitespace) that would otherwise pollute embeddings.
"""

import re
import unicodedata
from collections import Counter

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_BLANK_LINES_RE = re.compile(r"\n{3,}")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_TRAILING_SPACE_RE = re.compile(r"[ \t]+\n")
_PAGE_NUMBER_LINE_RE = re.compile(r"^\s*(?:page\s*)?\d{1,4}\s*(?:/\s*\d{1,4})?\s*$", re.IGNORECASE)

# A line repeated on at least this fraction of pages is treated as a
# running header/footer rather than content.
_HEADER_FOOTER_REPETITION_THRESHOLD = 0.6


def clean_page_text(text: str) -> str:
    """Normalize a single page/document's text. Order matters: normalize -> strip
    control chars -> collapse whitespace."""
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL_CHARS_RE.sub("", text)
    text = _TRAILING_SPACE_RE.sub("\n", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def strip_repeated_headers_footers(pages: list[str]) -> list[str]:
    """Removes lines that recur across a majority of pages (running headers/footers)
    and page-number-only lines. No-op for single-page documents (nothing to compare)."""
    if len(pages) < 2:
        return [
            "\n".join(line for line in page.splitlines() if not _PAGE_NUMBER_LINE_RE.match(line))
            for page in pages
        ]

    line_page_counts: Counter[str] = Counter()
    for page in pages:
        seen_this_page: set[str] = set()
        for line in page.splitlines():
            stripped = line.strip()
            if stripped and stripped not in seen_this_page:
                line_page_counts[stripped] += 1
                seen_this_page.add(stripped)

    min_repetitions = max(2, int(len(pages) * _HEADER_FOOTER_REPETITION_THRESHOLD))
    repeated_lines = {line for line, count in line_page_counts.items() if count >= min_repetitions}

    cleaned_pages = []
    for page in pages:
        kept_lines = [
            line
            for line in page.splitlines()
            if line.strip() not in repeated_lines and not _PAGE_NUMBER_LINE_RE.match(line)
        ]
        cleaned_pages.append("\n".join(kept_lines))
    return cleaned_pages


def clean_document_pages(pages: list[str]) -> list[str]:
    """Full cleaning pipeline for a multi-page document: per-page normalization,
    then cross-page header/footer stripping."""
    normalized = [clean_page_text(page) for page in pages]
    deduped = strip_repeated_headers_footers(normalized)
    return [clean_page_text(page) for page in deduped]
