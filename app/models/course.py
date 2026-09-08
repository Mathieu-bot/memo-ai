from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    quizzes = relationship(
        "Quiz",
        back_populates="course",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    videos = relationship(
        "Video",
        back_populates="course",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    notes = relationship(
        "Note",
        back_populates="course",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
