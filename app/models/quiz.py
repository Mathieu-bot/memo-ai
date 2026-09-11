from uuid import uuid4

from sqlalchemy import Column, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import relationship

from app.database import Base


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Uuid, primary_key=True, default=uuid4, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    course_id = Column(
        Uuid, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )

    course = relationship("Course", back_populates="quizzes")
    questions = relationship(
        "Question",
        back_populates="quiz",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
