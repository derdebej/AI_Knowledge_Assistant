"""Registration and login. See specs/API.md §1."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.di import SettingsDep, get_auth_service
from app.schemas.auth import LoginRequest, RegisterRequest, RegisterResponse, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=RegisterResponse)
async def register(payload: RegisterRequest, auth_service: AuthServiceDep) -> RegisterResponse:
    user = await auth_service.register(
        email=payload.email, password=payload.password, full_name=payload.full_name
    )
    return RegisterResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, auth_service: AuthServiceDep, settings: SettingsDep
) -> TokenResponse:
    access_token = await auth_service.login(email=payload.email, password=payload.password)
    return TokenResponse(access_token=access_token, expires_in=settings.jwt_expire_minutes * 60)
