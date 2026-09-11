from uuid import uuid4

from sqlalchemy import Column, ForeignKey, Text, Uuid
from sqlalchemy.orm import relationship

from app.database import Base


class Question(Base):
    __tablename__ = "questions"

    id = Column(Uuid, primary_key=True, default=uuid4, index=True)
    text = Column(Text, nullable=False)
    explanation = Column(Text, nullable=True)
    quiz_id = Column(
        Uuid, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    quiz = relationship("Quiz", back_populates="questions")
    answers = relationship(
        "Answer",
        back_populates="question",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
