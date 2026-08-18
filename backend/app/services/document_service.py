"""See specs/ARCHITECTURE.md §5.1 and §2.3."""

import uuid

from app.core.config import Settings
from app.documents.storage import LocalFileStorage
from app.documents.validation import sanitize_filename, validate_upload
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository


class DocumentService:
    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        storage: LocalFileStorage,
        settings: Settings,
    ) -> None:
        self._document_repository = document_repository
        self._storage = storage
        self._settings = settings

    async def upload(
        self, *, user_id: uuid.UUID, original_filename: str, file_bytes: bytes
    ) -> Document:
        """Validates and persists an uploaded file. Raises `UnsupportedFileTypeError`
        or `FileTooLargeError` (specs/SECURITY.md §1) - callers translate these to
        HTTP responses, this layer stays framework-free."""
        sniffed_mime = validate_upload(
            original_filename=original_filename, file_bytes=file_bytes, settings=self._settings
        )
        sanitized_filename = sanitize_filename(original_filename)
        document_id = uuid.uuid4()

        storage_path = self._storage.save(
            document_id=document_id, sanitized_filename=sanitized_filename, file_bytes=file_bytes
        )

        document = await self._document_repository.create(
            document_id=document_id,
            user_id=user_id,
            filename=sanitized_filename,
            original_filename=original_filename,
            content_type=sniffed_mime,
            file_size_bytes=len(file_bytes),
            storage_path=storage_path,
        )
        # Committed here, not left to the request's end-of-request commit -
        # the caller schedules background processing right after this
        # returns, and that background task needs the row to already be
        # durably visible. See DocumentRepository.commit().
        await self._document_repository.commit()
        return document

    async def get(self, document_id: uuid.UUID, *, user_id: uuid.UUID) -> Document | None:
        return await self._document_repository.get_by_id(document_id, user_id=user_id)

    async def list(
        self, *, user_id: uuid.UUID, status: str | None, limit: int, offset: int
    ) -> tuple[list[Document], int]:
        return await self._document_repository.list_for_user(
            user_id=user_id, status=status, limit=limit, offset=offset
        )

    async def delete(self, document_id: uuid.UUID, *, user_id: uuid.UUID) -> bool:
        document = await self._document_repository.get_by_id(document_id, user_id=user_id)
        if document is None:
            return False
        # Captured before delete/flush: the ORM instance's attributes are expired
        # (and unreadable without a now-impossible reload) once the row is gone.
        storage_path = document.storage_path
        deleted = await self._document_repository.delete(document_id, user_id=user_id)
        if deleted:
            self._storage.delete(storage_path)
        return deleted
