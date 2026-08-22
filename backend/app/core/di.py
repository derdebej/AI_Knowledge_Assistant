"""Dependency-injection wiring: which concrete adapter implements which port,
and how services/repositories are constructed per request. See
specs/ARCHITECTURE.md §2.8. This is the single place that decision is made -
swapping an adapter means changing a line here, not in services/api.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.documents.storage import LocalFileStorage
from app.domain.ports import Chunker, EmbeddingProvider
from app.rag.chunking.recursive_chunker import RecursiveCharacterChunker
from app.rag.embeddings.openai_embedding_provider import OpenAIEmbeddingProvider
from app.rag.vector_store.pgvector_store import PgVectorStore
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.document_service import DocumentService
from app.services.ingestion_service import IngestionService
from app.services.retrieval_service import RetrievalService

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


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=get_settings().openai_api_key)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    return OpenAIEmbeddingProvider(client=get_openai_client(), model=settings.embedding_model)


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


def get_ingestion_service(
    chunker: Annotated[Chunker, Depends(get_chunker)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> IngestionService:
    return IngestionService(
        chunker=chunker, embedding_provider=embedding_provider, vector_store_factory=PgVectorStore
    )


def get_retrieval_service(
    session: SessionDep,
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    settings: SettingsDep,
) -> RetrievalService:
    return RetrievalService(
        embedding_provider=embedding_provider,
        vector_store=PgVectorStore(session),
        top_k=settings.retrieval_top_k,
        relevance_threshold=settings.relevance_threshold,
    )
