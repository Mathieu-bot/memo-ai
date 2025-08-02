from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class VideoBase(BaseModel):
    title: str
    description: Optional[str] = None
    course_id: int

class VideoCreate(VideoBase):
    pass

class VideoUpload(VideoBase):
    pass

class VideoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    course_id: Optional[int] = None

class VideoInDBBase(VideoBase):
    id: int
    cloudinary_public_id: str
    cloudinary_url: str
    duration: Optional[int] = None
    transcript: Optional[str] = None
    created_at: datetime
    is_synchronized: bool

    class Config:
        orm_mode = True

class Video(VideoInDBBase):
    pass

class VideoWithTranscript(Video):
    pass