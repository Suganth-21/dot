from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PhotoUploadResponse(BaseModel):
    photo_hash: str = Field(serialization_alias="photoHash")
    url: str

    model_config = ConfigDict(populate_by_name=True)
