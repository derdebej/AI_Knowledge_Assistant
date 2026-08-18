"""Liveness/readiness endpoints. See specs/API.md §4.

Readiness (DB connectivity check) is added once app/db/session.py exists
(specs/ROADMAP.md Phase 2) - this module currently provides liveness only.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
