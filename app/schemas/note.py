from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NoteBase(BaseModel):
    title: str
    content: str
    course_id: int


class NoteCreate(NoteBase):
    pass


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    course_id: int | None = None


class NoteInDBBase(NoteBase):
    id: int
    summary: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class Note(NoteInDBBase):
    pass


class NoteWithSummary(Note):
    pass
