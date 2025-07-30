
from pydantic import BaseModel
from typing import Optional, List
from app.schemas.question import Question

class QuizBase(BaseModel):
    title: str
    description: Optional[str] = None
    course_id: int

class QuizCreate(QuizBase):
    pass

class QuizUpdate(QuizBase):
    title: Optional[str] = None
    course_id: Optional[int] = None

class QuizInDBBase(QuizBase):
    id: int
    class Config:
        orm_mode = True

class Quiz(QuizInDBBase):
    pass

class QuizWithQuestions(Quiz):
    questions: List[Question] = []
    class Config:
        orm_mode = True
