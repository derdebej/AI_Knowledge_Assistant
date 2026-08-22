"""Password hashing and JWT encode/decode. See specs/SECURITY.md §4."""

import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import Settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(password, hashed_password)


def create_access_token(user_id: uuid.UUID, *, settings: Settings) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expires_at}
    encoded: str = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded


def decode_access_token(token: str, *, settings: Settings) -> uuid.UUID | None:
    """Returns the user id encoded in `token`, or `None` if the token is
    missing, malformed, expired, or signed with a different secret - callers
    treat all of these identically as "unauthenticated" (specs/API.md §1),
    never distinguishing the reason in the response."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None

    subject = payload.get("sub")
    if not isinstance(subject, str):
        return None
    try:
        return uuid.UUID(subject)
    except ValueError:
        return None
