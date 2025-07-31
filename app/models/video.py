from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.services.db import Base

class Video(Base):
    __tablename__ = 'videos'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    cloudinary_public_id = Column(String(255), nullable=False)
    cloudinary_url = Column(String(512), nullable=False)
    duration = Column(Integer, nullable=True)
    transcript = Column(Text, nullable=True)
    course_id = Column(Integer, ForeignKey('courses.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_synchronized = Column(Boolean, default=True)

    course = relationship("Course", back_populates="videos")
