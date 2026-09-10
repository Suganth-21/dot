"""Aggregates every route module under one router, mounted at /api in
app.main. See ARCHITECTURE.md §2 folder layout."""
from fastapi import APIRouter

from app.api.routes_alerts import router as alerts_router
from app.api.routes_analytics import router as analytics_router
from app.api.routes_auth import router as auth_router
from app.api.routes_batches import router as batches_router
from app.api.routes_demo import router as demo_router
from app.api.routes_entities import router as entities_router
from app.api.routes_health import router as health_router
from app.api.routes_manufacturer import router as manufacturer_router
from app.api.routes_notifications import router as notifications_router
from app.api.routes_pickups import router as pickups_router
from app.api.routes_public import router as public_router
from app.api.routes_reference import router as reference_router
from app.api.routes_regulator import router as regulator_router
from app.api.routes_returns import router as returns_router
from app.api.routes_uploads import router as uploads_router
from app.api.ws import router as ws_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(reference_router, tags=["reference"])
api_router.include_router(regulator_router, tags=["regulator"])
api_router.include_router(batches_router, tags=["batches"])
api_router.include_router(demo_router, tags=["demo"])
api_router.include_router(alerts_router, tags=["alerts"])
api_router.include_router(returns_router, tags=["returns"])
api_router.include_router(pickups_router, tags=["pickups"])
api_router.include_router(manufacturer_router, tags=["manufacturer"])
api_router.include_router(entities_router, tags=["entities"])
api_router.include_router(notifications_router, tags=["notifications"])
api_router.include_router(analytics_router, tags=["analytics"])
api_router.include_router(uploads_router, tags=["uploads"])
api_router.include_router(ws_router, tags=["realtime"])
# CLAUDE.md rule 4: mounted like any other router, never behind an
# app-wide auth middleware a public route would need to opt out of
# (ARCHITECTURE.md §6.6).
api_router.include_router(public_router, tags=["public"])
