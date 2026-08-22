"""FastAPI dependencies shared across routers.

`get_current_user_id` decodes the bearer JWT (specs/SECURITY.md §4) and
resolves the current user's id. Every document/chat repository method
already takes `user_id` (specs/ARCHITECTURE.md §2.6), so Phase 6 auth plugs
in at exactly this one function - no service, repository, or route
signature changes (see specs/ROADMAP.md Phase 6).
"""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.di import SessionDep, SettingsDep
from app.core.security import decode_access_token
from app.repositories.user_repository import UserRepository

# `auto_error=False` so a missing header raises our own 401 (matching the
# rest of the app's error handling) instead of FastAPI security's default
# response shape.
_bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
)


async def get_current_user_id(
    settings: SettingsDep,
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> uuid.UUID:
    if credentials is None:
        raise _UNAUTHENTICATED

    user_id = decode_access_token(credentials.credentials, settings=settings)
    if user_id is None:
        raise _UNAUTHENTICATED

    # Confirms the token's subject still resolves to a real, active user -
    # e.g. one deleted after the token was issued shouldn't stay usable
    # until expiry.
    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise _UNAUTHENTICATED

    return user_id


CurrentUserIdDep = Annotated[uuid.UUID, Depends(get_current_user_id)]
