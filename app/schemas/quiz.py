from pydantic import BaseModel, ConfigDict

from app.schemas.question import Question


class QuizBase(BaseModel):
    title: str
    description: str | None = None
    course_id: int


class QuizCreate(QuizBase):
    pass


class QuizUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    course_id: int | None = None


class QuizInDBBase(QuizBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class Quiz(QuizInDBBase):
    pass


class QuizWithQuestions(Quiz):
    questions: list[Question] = []
