from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.question import Question


class QuizBase(BaseModel):
    title: str
    description: str | None = None
    course_id: UUID


class QuizCreate(QuizBase):
    pass


class QuizUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    course_id: UUID | None = None


class QuizInDBBase(QuizBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class Quiz(QuizInDBBase):
    pass


class QuizWithQuestions(Quiz):
    questions: list[Question] = []
