"""GET /api/entities, GET /api/entities/{id}. HTTP layer only — see
`app.services.entity_service` (CLAUDE.md rule 7). ARCHITECTURE.md §8.9.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, require_permission
from app.models.user import User
from app.schemas.entity import EntityDetailOut, EntityOut
from app.services import entity_service

router = APIRouter()


@router.get("/entities", response_model=list[EntityOut])
async def list_entities(
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("entities:read")),
) -> list[EntityOut]:
    return await entity_service.list_entities(session)


@router.get("/entities/{entity_id}", response_model=EntityDetailOut)
async def get_entity(
    entity_id: str,
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("entities:read")),
) -> EntityDetailOut:
    return await entity_service.get_entity(session, entity_id)
