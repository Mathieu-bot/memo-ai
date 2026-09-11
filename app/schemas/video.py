from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VideoBase(BaseModel):
    title: str
    description: str | None = None
    course_id: UUID


class VideoCreate(VideoBase):
    pass


class VideoUpload(BaseModel):
    title: str
    description: str | None = None
    course_id: UUID


class VideoUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    course_id: UUID | None = None


class VideoInDBBase(VideoBase):
    id: UUID
    storage_key: str
    duration: int | None = None
    transcript: str | None = None
    created_at: datetime
    is_synchronized: bool
    # Computed at request time: presigned URL with B2, None with local storage.
    file_url: str | None = None
    model_config = ConfigDict(from_attributes=True)


class Video(VideoInDBBase):
    pass


class VideoWithTranscript(Video):
    pass
