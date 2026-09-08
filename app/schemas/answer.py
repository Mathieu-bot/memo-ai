from pydantic import BaseModel, ConfigDict


class AnswerBase(BaseModel):
    text: str
    is_correct: bool = False
    question_id: int


class AnswerCreate(AnswerBase):
    pass


class AnswerUpdate(BaseModel):
    text: str | None = None
    is_correct: bool | None = None
    question_id: int | None = None


class AnswerInDBBase(AnswerBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class Answer(AnswerInDBBase):
    pass
