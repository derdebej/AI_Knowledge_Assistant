"""Integration test fixtures: a real Postgres+pgvector database, migrated
once per session and truncated between tests. See specs/TESTING.md §3.

Uses a dedicated `ai_knowledge_assistant_test` database on the same
docker-compose `postgres` service so it never touches dev data.
"""

import os
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated

import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.deps import get_current_user_id
from app.core.di import get_chat_service, get_chunker, get_ingestion_service
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models.user import User
from app.rag.vector_store.pgvector_store import PgVectorStore
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.message_repository import MessageRepository
from app.services.chat_service import ChatService
from app.services.ingestion_service import IngestionService
from app.services.retrieval_service import RetrievalService
from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_TEST_DB_NAME = "ai_knowledge_assistant_test"
_MAINTENANCE_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/postgres"
TEST_DATABASE_URL = f"postgresql+asyncpg://postgres:postgres@localhost:5433/{_TEST_DB_NAME}"

_APP_TABLE_NAMES = [table.name for table in Base.metadata.sorted_tables]


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _migrated_test_database() -> AsyncGenerator[None]:
    maintenance_engine = create_async_engine(
        _MAINTENANCE_DATABASE_URL, isolation_level="AUTOCOMMIT"
    )
    async with maintenance_engine.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": _TEST_DB_NAME}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{_TEST_DB_NAME}"'))
    await maintenance_engine.dispose()

    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    try:
        alembic_cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
        # alembic's env.py runs asyncio.run() internally, which can't nest
        # inside pytest-asyncio's already-running loop - a separate thread
        # gives it its own loop.
        import asyncio

        await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url

    yield


@pytest_asyncio.fixture
async def test_engine(_migrated_test_database: None):
    # Function-scoped, not session-scoped: pytest-asyncio gives each test
    # function its own event loop, and an asyncpg connection (which this
    # engine's pool holds) can't be reused across event loops - a
    # session-scoped engine here produced "another operation is in progress"
    # errors from the second test onward.
    engine = create_async_engine(TEST_DATABASE_URL)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
def test_session_factory(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(_migrated_test_database: None) -> AsyncGenerator[None]:
    """Truncates before, not after: runs on a short-lived engine of its own
    rather than sharing the session-scoped `test_engine`'s pool, so it can't
    race a still-closing connection from the previous test's `client`/
    `db_session` fixtures (which produced 'another operation is in progress'
    asyncpg errors when this shared the pool and ran on teardown)."""
    cleanup_engine = create_async_engine(TEST_DATABASE_URL)
    async with cleanup_engine.begin() as conn:
        table_list = ", ".join(f'"{name}"' for name in _APP_TABLE_NAMES)
        await conn.execute(text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE"))
    await cleanup_engine.dispose()
    yield


@pytest_asyncio.fixture
async def db_session(
    test_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(email=f"{uuid.uuid4()}@test.local", hashed_password="unused", is_active=True)
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
def chat_llm_provider() -> FakeLLMProvider:
    """One instance shared by every request the `client` fixture makes in a
    given test, so a test can both configure its canned response ahead of
    time and inspect `.received_prompts` afterward - see
    tests/integration/test_chat_api.py."""
    return FakeLLMProvider(response="This is a fake answer.")


@pytest_asyncio.fixture
async def client(
    test_session_factory: async_sessionmaker[AsyncSession],
    test_user: User,
    chat_llm_provider: FakeLLMProvider,
) -> AsyncGenerator[AsyncClient]:
    async def override_get_db_session() -> AsyncGenerator[AsyncSession]:
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_get_current_user_id() -> uuid.UUID:
        return user_id

    def override_get_ingestion_service() -> IngestionService:
        # Real chunker, real PgVectorStore (against the real test DB) - only
        # the embedding provider is faked, per specs/TESTING.md §3, so tests
        # never hit the real OpenAI API but still exercise real pgvector
        # storage/retrieval.
        return IngestionService(
            chunker=get_chunker(),
            embedding_provider=FakeEmbeddingProvider(),
            vector_store_factory=PgVectorStore,
            session_factory=test_session_factory,
        )

    async def override_get_chat_service(
        session: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> ChatService:
        # Same idea as `override_get_ingestion_service`: real repositories/
        # PgVectorStore against the real test DB, only the embedding/LLM
        # providers are faked. `Depends(get_db_session)` (the original, not
        # `override_get_db_session` directly) is what FastAPI's override
        # mechanism keys its per-request cache on, so this shares the exact
        # same session as every other SessionDep-based dependency in the
        # request - required for the streaming endpoint, where the user
        # message write and the retrieval read must see each other.
        settings = get_settings()
        return ChatService(
            retrieval_service=RetrievalService(
                embedding_provider=FakeEmbeddingProvider(),
                vector_store=PgVectorStore(session),
                top_k=settings.retrieval_top_k,
                relevance_threshold=settings.relevance_threshold,
            ),
            llm_provider=chat_llm_provider,
            document_repository=DocumentRepository(session),
            conversation_repository=ConversationRepository(session),
            message_repository=MessageRepository(session),
        )

    user_id = test_user.id
    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_current_user_id] = override_get_current_user_id
    app.dependency_overrides[get_ingestion_service] = override_get_ingestion_service
    app.dependency_overrides[get_chat_service] = override_get_chat_service
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as async_client:
            yield async_client
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def real_auth_client(
    test_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient]:
    """Like `client`, but does NOT override `get_current_user_id` - identity
    comes from a real register/login flow and a real bearer token, for
    testing the JWT dependency itself (specs/ROADMAP.md Phase 6) rather than
    bypassing it. Only `get_db_session` (point at the test DB) and
    `get_ingestion_service` (fake embeddings, so an upload in one of these
    tests doesn't hit real OpenAI) are overridden."""

    async def override_get_db_session() -> AsyncGenerator[AsyncSession]:
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def override_get_ingestion_service() -> IngestionService:
        return IngestionService(
            chunker=get_chunker(),
            embedding_provider=FakeEmbeddingProvider(),
            vector_store_factory=PgVectorStore,
            session_factory=test_session_factory,
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_ingestion_service] = override_get_ingestion_service
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as async_client:
            yield async_client
    finally:
        app.dependency_overrides.clear()
