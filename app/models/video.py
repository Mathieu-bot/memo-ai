from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.services.db import Base

class Video(Base):
    __tablename__ = 'videos'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    cloudinary_public_id = Column(String(255), nullable=False, index=True)
    cloudinary_url = Column(Text, nullable=False)
    duration = Column(Integer, nullable=True)
    transcript = Column(Text, nullable=True)
    course_id = Column(Integer, ForeignKey('courses.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_synchronized = Column(Boolean, default=True)

    course = relationship("Course", back_populates="videos")

    __table_args__ = (
        CheckConstraint('duration > 0', name='check_duration_positive'),
        CheckConstraint("cloudinary_url ~* '^https?://'", name='check_valid_url'),
        CheckConstraint("cloudinary_public_id ~* '^[a-zA-Z0-9_-]+$'", name='check_valid_public_id'),
    )

    def __repr__(self):
        return f"<Video(id={self.id}, title='{self.title}', course_id={self.course_id})>"