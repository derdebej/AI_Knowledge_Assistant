"""Conversation + message API endpoints against the real app + a real
database - full lifecycle, SSE event sequence, and ownership rejection.
See specs/TESTING.md §3, specs/API.md §3, and specs/ROADMAP.md Phase 5.
"""

import json
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.rag.prompting.prompt_builder import NOT_FOUND_MESSAGE
from app.repositories.document_repository import DocumentRepository
from tests.fakes import FakeLLMProvider

_KNOWN_CONTENT = b"The mitochondria is the powerhouse of the cell."


def _parse_sse_events(text: str) -> list[tuple[str | None, dict | None]]:
    events: list[tuple[str | None, dict | None]] = []
    for block in text.strip("\n").split("\n\n"):
        if not block:
            continue
        event_name: str | None = None
        data: dict | None = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
        events.append((event_name, data))
    return events


async def _create_document_for_another_user(db_session: AsyncSession) -> uuid.UUID:
    other_user = User(email=f"{uuid.uuid4()}@test.local", hashed_password="unused", is_active=True)
    db_session.add(other_user)
    await db_session.flush()

    document = await DocumentRepository(db_session).create(
        document_id=uuid.uuid4(),
        user_id=other_user.id,
        filename="other.txt",
        original_filename="other.txt",
        content_type="text/plain",
        file_size_bytes=10,
        storage_path="/data/uploads/other/other.txt",
    )
    await db_session.commit()
    return document.id


class TestCreateConversation:
    async def test_create_without_document_ids_returns_201_with_empty_scope(
        self, client: AsyncClient
    ) -> None:
        response = await client.post("/api/v1/conversations", json={})

        assert response.status_code == 201
        body = response.json()
        assert body["document_ids"] == []
        assert body["title"] is None

    async def test_create_with_an_owned_document_id_returns_201(self, client: AsyncClient) -> None:
        upload = await client.post(
            "/api/v1/documents", files={"file": ("notes.txt", _KNOWN_CONTENT, "text/plain")}
        )
        document_id = upload.json()["id"]

        response = await client.post("/api/v1/conversations", json={"document_ids": [document_id]})

        assert response.status_code == 201
        assert response.json()["document_ids"] == [document_id]

    async def test_create_with_another_users_document_id_returns_400(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        other_document_id = await _create_document_for_another_user(db_session)

        response = await client.post(
            "/api/v1/conversations", json={"document_ids": [str(other_document_id)]}
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_DOCUMENT_SCOPE"


class TestListAndGetConversations:
    async def test_list_returns_created_conversations(self, client: AsyncClient) -> None:
        await client.post("/api/v1/conversations", json={})
        await client.post("/api/v1/conversations", json={})

        response = await client.get("/api/v1/conversations")

        assert response.status_code == 200
        assert response.json()["total"] == 2

    async def test_get_returns_conversation_detail(self, client: AsyncClient) -> None:
        create = await client.post("/api/v1/conversations", json={})
        conversation_id = create.json()["id"]

        response = await client.get(f"/api/v1/conversations/{conversation_id}")

        assert response.status_code == 200
        assert response.json()["id"] == conversation_id

    async def test_get_nonexistent_conversation_returns_404(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/conversations/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404
        assert response.json()["error_code"] == "CONVERSATION_NOT_FOUND"


class TestListMessages:
    async def test_new_conversation_has_no_messages(self, client: AsyncClient) -> None:
        create = await client.post("/api/v1/conversations", json={})
        conversation_id = create.json()["id"]

        response = await client.get(f"/api/v1/conversations/{conversation_id}/messages")

        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}

    async def test_messages_for_nonexistent_conversation_returns_404(
        self, client: AsyncClient
    ) -> None:
        response = await client.get(
            "/api/v1/conversations/00000000-0000-0000-0000-000000000000/messages"
        )

        assert response.status_code == 404


class TestPostMessage:
    async def test_question_validation_rejects_empty_content(self, client: AsyncClient) -> None:
        create = await client.post("/api/v1/conversations", json={})
        conversation_id = create.json()["id"]

        response = await client.post(
            f"/api/v1/conversations/{conversation_id}/messages", json={"content": ""}
        )

        assert response.status_code == 422

    async def test_post_to_nonexistent_conversation_returns_404_not_a_stream(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/conversations/00000000-0000-0000-0000-000000000000/messages",
            json={"content": "question"},
        )

        assert response.status_code == 404
        assert response.json()["error_code"] == "CONVERSATION_NOT_FOUND"

    async def test_known_answer_streams_tokens_then_citations_then_done(
        self, client: AsyncClient, chat_llm_provider: FakeLLMProvider
    ) -> None:
        upload = await client.post(
            "/api/v1/documents", files={"file": ("notes.txt", _KNOWN_CONTENT, "text/plain")}
        )
        document_id = upload.json()["id"]
        create = await client.post("/api/v1/conversations", json={"document_ids": [document_id]})
        conversation_id = create.json()["id"]

        response = await client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": _KNOWN_CONTENT.decode()},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = _parse_sse_events(response.text)

        event_names = [name for name, _ in events]
        assert event_names[-2:] == ["citations", "done"]
        assert event_names[:-2] == ["token"] * (len(event_names) - 2)

        token_text = "".join(data["content"] for name, data in events if name == "token" and data)
        assert token_text == "This is a fake answer."

        citations_data = next(data for name, data in events if name == "citations" and data)
        assert len(citations_data["citations"]) == 1
        citation = citations_data["citations"][0]
        assert citation["document_id"] == document_id
        assert citation["document_name"] == "notes.txt"
        assert citation["rank"] == 1

        done_data = next(data for name, data in events if name == "done" and data)
        message_id = done_data["message_id"]

        assert len(chat_llm_provider.received_prompts) == 1
        assert _KNOWN_CONTENT.decode() in chat_llm_provider.received_prompts[0]

        # Persisted transcript reflects both the user question and the
        # generated + cited assistant reply.
        history = await client.get(f"/api/v1/conversations/{conversation_id}/messages")
        items = history.json()["items"]
        assert [item["role"] for item in items] == ["user", "assistant"]
        assert items[0]["content"] == _KNOWN_CONTENT.decode()
        assert items[0]["citations"] is None
        assert items[1]["id"] == message_id
        assert items[1]["content"] == "This is a fake answer."
        assert items[1]["citations"][0]["document_id"] == document_id

    async def test_no_documents_at_all_short_circuits_to_not_found(
        self, client: AsyncClient, chat_llm_provider: FakeLLMProvider
    ) -> None:
        # No document uploaded in this test at all - zero chunks exist for
        # this user, guaranteeing the empty-retrieval path deterministically
        # rather than depending on fake-embedding similarity coincidences.
        create = await client.post("/api/v1/conversations", json={})
        conversation_id = create.json()["id"]

        response = await client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "What is the mitochondria?"},
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        assert [name for name, _ in events] == ["token", "citations", "done"]

        token_data = events[0][1]
        assert token_data is not None
        assert token_data["content"] == NOT_FOUND_MESSAGE
        citations_data = events[1][1]
        assert citations_data is not None
        assert citations_data["citations"] == []

        assert chat_llm_provider.received_prompts == []
