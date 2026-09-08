from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VideoBase(BaseModel):
    title: str
    description: str | None = None
    course_id: int


class VideoCreate(VideoBase):
    pass


class VideoUpload(BaseModel):
    title: str
    description: str | None = None
    course_id: int


class VideoUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    course_id: int | None = None


class VideoInDBBase(VideoBase):
    id: int
    cloudinary_public_id: str
    cloudinary_url: str
    duration: int | None = None
    transcript: str | None = None
    created_at: datetime
    is_synchronized: bool
    model_config = ConfigDict(from_attributes=True)


class Video(VideoInDBBase):
    pass


class VideoWithTranscript(Video):
    pass
