"""Upload validation: extension allowlist, content sniffing, size limit.

See specs/SECURITY.md §1. Content type is determined from the file's actual
bytes (via libmagic), never trusted from the client-supplied extension or
Content-Type header alone - this is what stops a renamed executable from
posing as a `.pdf`.
"""

import re

import magic

from app.core.config import Settings
from app.domain.exceptions import FileTooLargeError, UnsupportedFileTypeError

_EXTENSION_TO_MIME = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}

_UNSAFE_FILENAME_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]")


def sanitize_filename(original_filename: str) -> str:
    """Strips directory components and unsafe characters so the result is safe
    to use as a path segment (prevents path traversal - specs/SECURITY.md §1)."""
    base_name = original_filename.replace("\\", "/").rsplit("/", 1)[-1]
    return _UNSAFE_FILENAME_CHARS_RE.sub("_", base_name) or "upload"


def validate_upload(*, original_filename: str, file_bytes: bytes, settings: Settings) -> str:
    """Validates extension, sniffed content, and size. Returns the sniffed MIME type.

    Raises `UnsupportedFileTypeError` or `FileTooLargeError` on rejection.
    """
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise FileTooLargeError(f"File exceeds the {settings.max_upload_size_mb} MB limit.")
    if not file_bytes:
        raise UnsupportedFileTypeError("Uploaded file is empty.")

    extension = (
        "." + original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    )
    if extension not in settings.allowed_upload_extensions:
        raise UnsupportedFileTypeError(
            f"Extension '{extension}' is not allowed. Allowed: {settings.allowed_upload_extensions}."
        )

    sniffed_mime: str = magic.from_buffer(file_bytes, mime=True)
    expected_mime = _EXTENSION_TO_MIME[extension]
    if sniffed_mime != expected_mime:
        raise UnsupportedFileTypeError(
            f"File content ({sniffed_mime}) does not match its extension ({extension})."
        )

    return sniffed_mime
