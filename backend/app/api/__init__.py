"""Aggregates every route module under one router, mounted at /api in
app.main. See ARCHITECTURE.md §2 folder layout."""
from fastapi import APIRouter

from app.api.routes_auth import router as auth_router
from app.api.routes_batches import router as batches_router
from app.api.routes_demo import router as demo_router
from app.api.routes_health import router as health_router
from app.api.routes_reference import router as reference_router
from app.api.routes_regulator import router as regulator_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(reference_router, tags=["reference"])
api_router.include_router(regulator_router, tags=["regulator"])
api_router.include_router(batches_router, tags=["batches"])
api_router.include_router(demo_router, tags=["demo"])
