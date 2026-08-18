"""Dependency-injection wiring: which concrete adapter implements which port,
and how services/repositories are constructed per request. See
specs/ARCHITECTURE.md §2.8. This is the single place that decision is made -
swapping an adapter means changing a line here, not in services/api.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.documents.storage import LocalFileStorage
from app.domain.ports import Chunker
from app.rag.chunking.recursive_chunker import RecursiveCharacterChunker
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.document_service import DocumentService
from app.services.ingestion_service import IngestionService

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@lru_cache
def get_storage() -> LocalFileStorage:
    # Reads settings directly (itself a cached singleton) rather than via
    # FastAPI's Depends, since Settings isn't hashable and can't be an
    # lru_cache key.
    return LocalFileStorage(get_settings().upload_storage_path)


@lru_cache
def get_chunker() -> Chunker:
    settings = get_settings()
    return RecursiveCharacterChunker(
        chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
    )


def get_document_repository(session: SessionDep) -> DocumentRepository:
    return DocumentRepository(session)


def get_chunk_repository(session: SessionDep) -> ChunkRepository:
    return ChunkRepository(session)


def get_document_service(
    document_repository: Annotated[DocumentRepository, Depends(get_document_repository)],
    storage: Annotated[LocalFileStorage, Depends(get_storage)],
    settings: SettingsDep,
) -> DocumentService:
    return DocumentService(
        document_repository=document_repository, storage=storage, settings=settings
    )


def get_ingestion_service(chunker: Annotated[Chunker, Depends(get_chunker)]) -> IngestionService:
    return IngestionService(chunker=chunker)
