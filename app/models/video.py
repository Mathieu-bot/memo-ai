from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    storage_key = Column(String(512), nullable=False, index=True)
    duration = Column(Integer, nullable=True)
    transcript = Column(Text, nullable=True)
    course_id = Column(
        Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    is_synchronized = Column(Boolean, default=True)

    course = relationship("Course", back_populates="videos")
