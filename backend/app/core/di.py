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
from app.domain.ports import Chunker, EmbeddingProvider, LLMProvider
from app.rag.chunking.recursive_chunker import RecursiveCharacterChunker
from app.rag.embeddings.openai_embedding_provider import OpenAIEmbeddingProvider
from app.rag.llm.openai_llm_provider import OpenAILLMProvider
from app.rag.vector_store.pgvector_store import PgVectorStore
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
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
def get_embedding_client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(
        api_key=settings.embedding_api_key or settings.openai_api_key,
        base_url=settings.embedding_base_url,
    )


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    return OpenAIEmbeddingProvider(client=get_embedding_client(), model=settings.embedding_model)


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


@lru_cache
def get_llm_client() -> AsyncOpenAI:
    # Deliberately a separate client from get_embedding_client(): generation
    # can point at a different OpenAI-compatible endpoint (e.g. OpenRouter)
    # than embeddings without affecting embeddings, and vice versa.
    settings = get_settings()
    return AsyncOpenAI(
        api_key=settings.llm_api_key or settings.openai_api_key,
        base_url=settings.llm_base_url,
    )


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    return OpenAILLMProvider(
        client=get_llm_client(), model=settings.llm_model, temperature=settings.llm_temperature
    )


def get_user_repository(session: SessionDep) -> UserRepository:
    return UserRepository(session)


def get_auth_service(
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
    settings: SettingsDep,
) -> AuthService:
    return AuthService(user_repository=user_repository, settings=settings)


def get_conversation_repository(session: SessionDep) -> ConversationRepository:
    return ConversationRepository(session)


def get_message_repository(session: SessionDep) -> MessageRepository:
    return MessageRepository(session)


def get_chat_service(
    retrieval_service: Annotated[RetrievalService, Depends(get_retrieval_service)],
    llm_provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    document_repository: Annotated[DocumentRepository, Depends(get_document_repository)],
    conversation_repository: Annotated[
        ConversationRepository, Depends(get_conversation_repository)
    ],
    message_repository: Annotated[MessageRepository, Depends(get_message_repository)],
) -> ChatService:
    return ChatService(
        retrieval_service=retrieval_service,
        llm_provider=llm_provider,
        document_repository=document_repository,
        conversation_repository=conversation_repository,
        message_repository=message_repository,
    )
