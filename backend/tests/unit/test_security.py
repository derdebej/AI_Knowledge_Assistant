"""Password hashing and JWT encode/decode round-trips. See specs/TESTING.md
§2 and specs/SECURITY.md §4.
"""

import uuid
from datetime import UTC, datetime, timedelta

from jose import jwt as jose_jwt

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {"jwt_secret_key": "test-secret", "jwt_algorithm": "HS256"}
    return Settings(**(defaults | overrides))  # type: ignore[arg-type]


class TestPasswordHashing:
    def test_verify_password_succeeds_for_the_correct_password(self) -> None:
        hashed = hash_password("correct horse battery staple")

        assert verify_password("correct horse battery staple", hashed)

    def test_verify_password_fails_for_the_wrong_password(self) -> None:
        hashed = hash_password("correct horse battery staple")

        assert not verify_password("wrong password", hashed)

    def test_hash_is_never_the_plaintext_password(self) -> None:
        hashed = hash_password("correct horse battery staple")

        assert hashed != "correct horse battery staple"


class TestAccessToken:
    def test_decode_recovers_the_same_user_id_the_token_was_created_for(self) -> None:
        user_id = uuid.uuid4()
        settings = _settings()

        token = create_access_token(user_id, settings=settings)

        assert decode_access_token(token, settings=settings) == user_id

    def test_decode_rejects_a_token_signed_with_a_different_secret(self) -> None:
        user_id = uuid.uuid4()
        token = create_access_token(user_id, settings=_settings(jwt_secret_key="secret-a"))

        result = decode_access_token(token, settings=_settings(jwt_secret_key="secret-b"))

        assert result is None

    def test_decode_rejects_an_expired_token(self) -> None:
        # Hand-crafted with an already-past `exp`, rather than waiting on a
        # real clock (deterministic, no sleep).
        settings = _settings()
        expired_payload = {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        }
        expired_token = jose_jwt.encode(
            expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        assert decode_access_token(expired_token, settings=settings) is None

    def test_decode_rejects_garbage_input(self) -> None:
        assert decode_access_token("not-a-real-token", settings=_settings()) is None
