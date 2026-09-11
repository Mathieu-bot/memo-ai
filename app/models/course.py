from uuid import uuid4

from sqlalchemy import Column, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import relationship

from app.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(Uuid, primary_key=True, default=uuid4, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    owner = relationship("User", back_populates="owned_courses")
    members = relationship(
        "CourseMember",
        back_populates="course",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
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
