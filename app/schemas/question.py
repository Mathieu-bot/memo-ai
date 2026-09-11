from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.answer import Answer


class QuestionBase(BaseModel):
    text: str
    explanation: str | None = None
    quiz_id: UUID


class QuestionCreate(QuestionBase):
    pass


class QuestionUpdate(BaseModel):
    text: str | None = None
    explanation: str | None = None
    quiz_id: UUID | None = None


class QuestionInDBBase(QuestionBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class Question(QuestionInDBBase):
    pass


class QuestionWithAnswers(Question):
    answers: list[Answer] = []
