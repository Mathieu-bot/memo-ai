from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnswerBase(BaseModel):
    text: str
    is_correct: bool = False
    question_id: UUID


class AnswerCreate(AnswerBase):
    pass


class AnswerUpdate(BaseModel):
    text: str | None = None
    is_correct: bool | None = None
    question_id: UUID | None = None


class AnswerInDBBase(AnswerBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class Answer(AnswerInDBBase):
    pass
