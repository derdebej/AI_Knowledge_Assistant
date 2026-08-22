"""Registration and login use cases. See specs/API.md §1 and specs/SECURITY.md §4."""

from app.core.config import Settings
from app.core.security import create_access_token, hash_password, verify_password
from app.domain.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError
from app.models.user import User
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, *, user_repository: UserRepository, settings: Settings) -> None:
        self._user_repository = user_repository
        self._settings = settings

    async def register(self, *, email: str, password: str, full_name: str | None) -> User:
        existing = await self._user_repository.get_by_email(email)
        if existing is not None:
            raise EmailAlreadyRegisteredError("Email is already registered")
        return await self._user_repository.create(
            email=email, hashed_password=hash_password(password), full_name=full_name
        )

    async def login(self, *, email: str, password: str) -> str:
        user = await self._user_repository.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("Invalid email or password")
        return create_access_token(user.id, settings=self._settings)
