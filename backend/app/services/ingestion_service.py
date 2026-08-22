"""Extract -> clean -> chunk -> embed -> store pipeline. See
specs/RAG_PIPELINE.md §1 and specs/ARCHITECTURE.md §5.1.

Runs inside a `BackgroundTasks` callback (specs/ARCHITECTURE.md §7), so it
owns its own DB session rather than receiving one via request-scoped DI - the
request's session is long gone by the time this executes. `VectorStore` needs
that same session, so it's constructed here via an injected factory (mirrors
how `ChunkRepository`/`DocumentRepository` are constructed inline below)
rather than passed in as a ready-made instance - see specs/TESTING.md §2 for
why this needs to stay swappable for a fake in unit tests.
"""

import asyncio
import uuid
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.documents.cleaning import clean_document_pages
from app.documents.parsers.factory import get_parser
from app.domain.entities import ChunkData
from app.domain.exceptions import DomainError
from app.domain.ports import Chunker, EmbeddingProvider, VectorStore
from app.models.document import DocumentStatus
from app.rag.vector_store.pgvector_store import PgVectorStore
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository

logger = get_logger(__name__)


class IngestionService:
    def __init__(
        self,
        *,
        chunker: Chunker,
        embedding_provider: EmbeddingProvider,
        vector_store_factory: Callable[[AsyncSession], VectorStore] = PgVectorStore,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
    ) -> None:
        self._chunker = chunker
        self._embedding_provider = embedding_provider
        self._vector_store_factory = vector_store_factory
        # Injectable rather than importing AsyncSessionLocal at call time -
        # otherwise tests that override `get_db_session` for the API layer
        # would have no way to also redirect this background-task session,
        # since it's constructed outside FastAPI's dependency system.
        self._session_factory = session_factory

    async def process(self, document_id: uuid.UUID, *, user_id: uuid.UUID) -> None:
        async with self._session_factory() as session:
            document_repository = DocumentRepository(session)
            chunk_repository = ChunkRepository(session)

            document = await document_repository.get_by_id(document_id, user_id=user_id)
            if document is None:
                return  # deleted before processing started

            await document_repository.update_status(
                document_id, user_id=user_id, status=DocumentStatus.PROCESSING
            )
            await session.commit()

            try:
                file_bytes = await asyncio.to_thread(Path(document.storage_path).read_bytes)
                parser = get_parser(document.content_type)
                extracted = parser.extract(file_bytes)

                cleaned_pages = clean_document_pages([page.text for page in extracted.pages])

                all_chunks: list[ChunkData] = []
                for page, cleaned_text in zip(extracted.pages, cleaned_pages, strict=True):
                    base_metadata: dict[str, object] = {
                        "original_filename": document.original_filename,
                        "page_number": page.page_number,
                    }
                    all_chunks.extend(
                        self._chunker.split(cleaned_text, base_metadata=base_metadata)
                    )

                # Each page was chunked independently (chunk_index restarts at 0
                # per page) - renumber sequentially across the whole document to
                # satisfy the UNIQUE(document_id, chunk_index) constraint.
                renumbered_chunks = [
                    ChunkData(
                        chunk_index=index,
                        content=chunk.content,
                        token_count=chunk.token_count,
                        metadata=chunk.metadata,
                    )
                    for index, chunk in enumerate(all_chunks)
                ]

                chunk_rows = await chunk_repository.replace_all_for_document(
                    document_id, renumbered_chunks
                )

                # Document reaches `completed` only once embeddings are
                # actually stored, not merely once chunks exist - see
                # specs/ROADMAP.md Phase 3.
                embeddings = await self._embedding_provider.embed(
                    [chunk.content for chunk in chunk_rows]
                )
                vector_store = self._vector_store_factory(session)
                await vector_store.upsert_embeddings(
                    [str(chunk.id) for chunk in chunk_rows], embeddings
                )

                await document_repository.update_status(
                    document_id,
                    user_id=user_id,
                    status=DocumentStatus.COMPLETED,
                    page_count=extracted.page_count,
                )
                await session.commit()
            except DomainError as exc:
                await session.rollback()
                logger.warning(
                    "document_ingestion_failed",
                    document_id=str(document_id),
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                await document_repository.update_status(
                    document_id,
                    user_id=user_id,
                    status=DocumentStatus.FAILED,
                    error_message=str(exc),
                )
                await session.commit()
            except Exception as exc:
                # Broader than DomainError on purpose: embedding/storage calls
                # (specs/RAG_PIPELINE.md §1.6-1.7) can fail with provider/
                # network errors that aren't domain exceptions, and this is
                # the top of the background task - nothing above it can catch
                # these, so left uncaught the document would be stuck at
                # `processing` forever. The full error is logged server-side
                # only; the persisted `error_message` stays generic per
                # specs/SECURITY.md (no internal detail in a user-facing field).
                await session.rollback()
                logger.error(
                    "document_ingestion_failed_unexpected",
                    document_id=str(document_id),
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                await document_repository.update_status(
                    document_id,
                    user_id=user_id,
                    status=DocumentStatus.FAILED,
                    error_message="An unexpected error occurred while processing this document.",
                )
                await session.commit()
