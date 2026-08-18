"""Local disk storage for uploaded files. See specs/DATABASE.md §7.

Object storage (S3/MinIO) is deferred to post-MVP (specs/ROADMAP.md); this is
the one place that decision would be swapped in, since callers only deal with
`storage_path` strings and bytes.
"""

import uuid
from pathlib import Path


class LocalFileStorage:
    def __init__(self, root: str) -> None:
        self._root = Path(root)

    def save(self, *, document_id: uuid.UUID, sanitized_filename: str, file_bytes: bytes) -> str:
        """Writes the file under `{root}/{document_id}/{sanitized_filename}` and
        returns the path to store in `documents.storage_path`."""
        document_dir = self._root / str(document_id)
        document_dir.mkdir(parents=True, exist_ok=True)
        file_path = document_dir / sanitized_filename
        file_path.write_bytes(file_bytes)
        return str(file_path)

    def delete(self, storage_path: str) -> None:
        """Removes the file and its parent `{document_id}` directory if now empty.
        A missing file is not an error - deletion is idempotent."""
        path = Path(storage_path)
        path.unlink(missing_ok=True)
        parent = path.parent
        if parent != self._root and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
