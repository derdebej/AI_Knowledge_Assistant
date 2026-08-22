"""Auth API against the real app + a real database: register/login flow,
protected-route rejection without a token, and cross-user data isolation
now that a real JWT dependency protects every route. Uses `real_auth_client`
(unlike every other integration test file) since identity here must come
from an actual token, not the placeholder override. See specs/API.md §1,
specs/SECURITY.md §3-4, and specs/ROADMAP.md Phase 6.
"""

import uuid

from httpx import AsyncClient


async def _register_and_login(
    client: AsyncClient, *, email: str, password: str = "password123"
) -> str:
    register = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    assert register.status_code == 201, register.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token: str = login.json()["access_token"]
    return token


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestRegister:
    async def test_register_returns_201_with_user_data(self, real_auth_client: AsyncClient) -> None:
        response = await real_auth_client.post(
            "/api/v1/auth/register",
            json={
                "email": f"{uuid.uuid4()}@example.com",
                "password": "password123",
                "full_name": "Ada Lovelace",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["full_name"] == "Ada Lovelace"
        assert "password" not in body
        assert "hashed_password" not in body

    async def test_register_duplicate_email_returns_409(
        self, real_auth_client: AsyncClient
    ) -> None:
        email = f"{uuid.uuid4()}@example.com"
        await real_auth_client.post(
            "/api/v1/auth/register", json={"email": email, "password": "password123"}
        )

        response = await real_auth_client.post(
            "/api/v1/auth/register", json={"email": email, "password": "password123"}
        )

        assert response.status_code == 409
        assert response.json()["error_code"] == "EMAIL_ALREADY_REGISTERED"

    async def test_register_rejects_too_short_password(self, real_auth_client: AsyncClient) -> None:
        response = await real_auth_client.post(
            "/api/v1/auth/register",
            json={"email": f"{uuid.uuid4()}@example.com", "password": "short"},
        )

        assert response.status_code == 422

    async def test_register_rejects_invalid_email(self, real_auth_client: AsyncClient) -> None:
        response = await real_auth_client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "password123"},
        )

        assert response.status_code == 422


class TestLogin:
    async def test_login_returns_a_bearer_access_token(self, real_auth_client: AsyncClient) -> None:
        email = f"{uuid.uuid4()}@example.com"
        await real_auth_client.post(
            "/api/v1/auth/register", json={"email": email, "password": "password123"}
        )

        response = await real_auth_client.post(
            "/api/v1/auth/login", json={"email": email, "password": "password123"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["expires_in"] > 0

    async def test_login_with_wrong_password_returns_401(
        self, real_auth_client: AsyncClient
    ) -> None:
        email = f"{uuid.uuid4()}@example.com"
        await real_auth_client.post(
            "/api/v1/auth/register", json={"email": email, "password": "password123"}
        )

        response = await real_auth_client.post(
            "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
        )

        assert response.status_code == 401
        assert response.json()["error_code"] == "INVALID_CREDENTIALS"

    async def test_login_with_unknown_email_returns_401(
        self, real_auth_client: AsyncClient
    ) -> None:
        response = await real_auth_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "password123"},
        )

        assert response.status_code == 401
        assert response.json()["error_code"] == "INVALID_CREDENTIALS"


class TestProtectedRoutes:
    async def test_request_without_a_token_returns_401(self, real_auth_client: AsyncClient) -> None:
        response = await real_auth_client.get("/api/v1/documents")

        assert response.status_code == 401

    async def test_request_with_a_garbage_token_returns_401(
        self, real_auth_client: AsyncClient
    ) -> None:
        response = await real_auth_client.get(
            "/api/v1/documents", headers=_auth_header("not-a-real-token")
        )

        assert response.status_code == 401

    async def test_request_with_a_valid_token_succeeds(self, real_auth_client: AsyncClient) -> None:
        token = await _register_and_login(real_auth_client, email=f"{uuid.uuid4()}@example.com")

        response = await real_auth_client.get("/api/v1/documents", headers=_auth_header(token))

        assert response.status_code == 200


class TestCrossUserIsolation:
    async def test_user_b_cannot_read_user_as_document(self, real_auth_client: AsyncClient) -> None:
        token_a = await _register_and_login(real_auth_client, email=f"{uuid.uuid4()}@example.com")
        upload = await real_auth_client.post(
            "/api/v1/documents",
            files={"file": ("notes.txt", b"hello world", "text/plain")},
            headers=_auth_header(token_a),
        )
        document_id = upload.json()["id"]

        token_b = await _register_and_login(real_auth_client, email=f"{uuid.uuid4()}@example.com")
        response = await real_auth_client.get(
            f"/api/v1/documents/{document_id}", headers=_auth_header(token_b)
        )

        assert response.status_code == 404

    async def test_user_b_cannot_delete_user_as_document(
        self, real_auth_client: AsyncClient
    ) -> None:
        token_a = await _register_and_login(real_auth_client, email=f"{uuid.uuid4()}@example.com")
        upload = await real_auth_client.post(
            "/api/v1/documents",
            files={"file": ("notes.txt", b"hello world", "text/plain")},
            headers=_auth_header(token_a),
        )
        document_id = upload.json()["id"]

        token_b = await _register_and_login(real_auth_client, email=f"{uuid.uuid4()}@example.com")
        response = await real_auth_client.delete(
            f"/api/v1/documents/{document_id}", headers=_auth_header(token_b)
        )

        assert response.status_code == 404

        # And user A can still see it - proves the 404 was ownership
        # scoping, not the document having actually been deleted.
        still_there = await real_auth_client.get(
            f"/api/v1/documents/{document_id}", headers=_auth_header(token_a)
        )
        assert still_there.status_code == 200

    async def test_user_b_cannot_read_user_as_conversation(
        self, real_auth_client: AsyncClient
    ) -> None:
        token_a = await _register_and_login(real_auth_client, email=f"{uuid.uuid4()}@example.com")
        create = await real_auth_client.post(
            "/api/v1/conversations", json={}, headers=_auth_header(token_a)
        )
        conversation_id = create.json()["id"]

        token_b = await _register_and_login(real_auth_client, email=f"{uuid.uuid4()}@example.com")
        response = await real_auth_client.get(
            f"/api/v1/conversations/{conversation_id}", headers=_auth_header(token_b)
        )

        assert response.status_code == 404

    async def test_user_b_cannot_scope_a_conversation_to_user_as_document(
        self, real_auth_client: AsyncClient
    ) -> None:
        token_a = await _register_and_login(real_auth_client, email=f"{uuid.uuid4()}@example.com")
        upload = await real_auth_client.post(
            "/api/v1/documents",
            files={"file": ("notes.txt", b"hello world", "text/plain")},
            headers=_auth_header(token_a),
        )
        document_id = upload.json()["id"]

        token_b = await _register_and_login(real_auth_client, email=f"{uuid.uuid4()}@example.com")
        response = await real_auth_client.post(
            "/api/v1/conversations",
            json={"document_ids": [document_id]},
            headers=_auth_header(token_b),
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_DOCUMENT_SCOPE"
