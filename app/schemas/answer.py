from pydantic import BaseModel
from typing import Optional

class AnswerBase(BaseModel):
    text: str
    is_correct: bool = False
    question_id: int

class AnswerCreate(AnswerBase):
    pass

class AnswerUpdate(AnswerBase):
    text: Optional[str] = None
    is_correct: Optional[bool] = None
    question_id: Optional[int] = None

class AnswerInDBBase(AnswerBase):
    id: int

    class Config:
        orm_mode = True

class Answer(AnswerInDBBase):
    pass
