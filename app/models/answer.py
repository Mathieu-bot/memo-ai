from uuid import uuid4

from sqlalchemy import Boolean, Column, ForeignKey, Text, Uuid
from sqlalchemy.orm import relationship

from app.database import Base


class Answer(Base):
    __tablename__ = "answers"

    id = Column(Uuid, primary_key=True, default=uuid4, index=True)
    text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)
    question_id = Column(
        Uuid, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    question = relationship("Question", back_populates="answers")
