"""POST /api/uploads/photo — Phase 9 real photo upload. Any authenticated
role may upload (a pharmacy's strip photo, a distributor's received-goods
photo, ...); the caller decides what to do with the returned `photoHash`.
See `app.services.upload_service`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile

from app.core.errors import ValidationFailed
from app.deps import get_current_user
from app.models.user import User
from app.schemas.upload import PhotoUploadResponse
from app.services.upload_service import UploadTooLarge, save_photo

router = APIRouter()


@router.post("/uploads/photo", response_model=PhotoUploadResponse)
async def upload_photo(
    file: UploadFile, _current_user: User = Depends(get_current_user),
) -> PhotoUploadResponse:
    content = await file.read()
    if not content:
        raise ValidationFailed("Uploaded file is empty.", code="EMPTY_UPLOAD")
    try:
        photo_hash, url = save_photo(content, file.filename)
    except UploadTooLarge as exc:
        raise ValidationFailed(str(exc), code="UPLOAD_TOO_LARGE") from exc
    return PhotoUploadResponse(photo_hash=photo_hash, url=url)
