from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VideoBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    course_id: UUID


class VideoUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    course_id: UUID | None = None

    @field_validator("title")
    @classmethod
    def _reject_null_title(cls, value):
        if value is None:
            raise ValueError("title must not be null; omit it instead")
        return value


class VideoInDBBase(VideoBase):
    id: UUID
    storage_key: str
    duration: int | None = None
    transcript: str | None = None
    created_at: datetime
    # Computed at request time: presigned URL with B2, None with local storage.
    file_url: str | None = None
    model_config = ConfigDict(from_attributes=True)


class Video(VideoInDBBase):
    pass


class VideoWithTranscript(Video):
    pass
