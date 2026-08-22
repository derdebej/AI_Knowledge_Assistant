"""Liveness/readiness endpoints. See specs/API.md §4."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready(
    response: Response, session: Annotated[AsyncSession, Depends(get_db_session)]
) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
        result = await session.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        if result.first() is None:
            raise RuntimeError("pgvector extension not installed")
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "database": "error"}
    return {"status": "ready", "database": "ok"}
