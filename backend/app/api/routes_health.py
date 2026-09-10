"""GET /api/health — a real database round-trip, not a hardcoded ok.

HTTP layer only: no business logic. If the round-trip fails, the failure is
reported honestly (503, db: "error") instead of a blind 200.
"""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.db import async_session_factory

logger = logging.getLogger("dot.health")

router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    settings = get_settings()

    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("health_db_round_trip_failed")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "service": settings.app_name,
                "db": "error",
                "version": settings.app_version,
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "service": settings.app_name,
            "db": "ok",
            "version": settings.app_version,
        },
    )
