from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

NOTE_CONTENT_MAX_LENGTH = 100_000


class NoteBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=NOTE_CONTENT_MAX_LENGTH)
    course_id: UUID


class NoteCreate(NoteBase):
    pass


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=NOTE_CONTENT_MAX_LENGTH)
    course_id: UUID | None = None

    @field_validator("title", "content")
    @classmethod
    def _reject_null(cls, value):
        if value is None:
            raise ValueError("field must not be null; omit it instead")
        return value


class NoteInDBBase(NoteBase):
    id: UUID
    summary: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class Note(NoteInDBBase):
    pass


class NoteWithSummary(Note):
    pass
