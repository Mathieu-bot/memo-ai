from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.question import Question


class QuizBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    course_id: UUID


class QuizCreate(QuizBase):
    pass


class QuizUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    course_id: UUID | None = None

    @field_validator("title")
    @classmethod
    def _reject_null_title(cls, value):
        if value is None:
            raise ValueError("title must not be null; omit it instead")
        return value


class QuizInDBBase(QuizBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class Quiz(QuizInDBBase):
    pass


class QuizWithQuestions(Quiz):
    questions: list[Question] = []
