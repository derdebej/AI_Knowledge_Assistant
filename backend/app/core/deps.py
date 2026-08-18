"""FastAPI dependencies shared across routers.

`get_current_user_id` is a **Phase 6 placeholder**: real JWT-based auth
(specs/ROADMAP.md Phase 6) will replace this with a dependency that decodes
the bearer token. Every document/chat repository method already takes
`user_id` (specs/ARCHITECTURE.md §2.6), so that swap touches only this
function - no service, repository, or route signature changes.
"""

import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select

from app.core.di import SessionDep
from app.models.user import User

_PLACEHOLDER_DEV_USER_EMAIL = "dev-placeholder@local"


async def get_current_user_id(session: SessionDep) -> uuid.UUID:
    result = await session.execute(select(User.id).where(User.email == _PLACEHOLDER_DEV_USER_EMAIL))
    user_id = result.scalar_one_or_none()
    if user_id is not None:
        return user_id

    user = User(
        email=_PLACEHOLDER_DEV_USER_EMAIL,
        hashed_password="unusable-placeholder-hash",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user.id


CurrentUserIdDep = Annotated[uuid.UUID, Depends(get_current_user_id)]
