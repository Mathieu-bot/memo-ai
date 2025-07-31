from pydantic import BaseModel
from typing import Optional, List
from app.schemas.answer import Answer

class QuestionBase(BaseModel):
    text: str
    explanation: Optional[str] = None
    quiz_id: int

class QuestionCreate(QuestionBase):
    pass

class QuestionUpdate(QuestionBase):
    text: Optional[str] = None
    quiz_id: Optional[int] = None

class QuestionInDBBase(QuestionBase):
    id: int

    class Config:
        orm_mode = True

class Question(QuestionInDBBase):
    pass

class QuestionWithAnswers(Question):
    answers: List[Answer] = []
