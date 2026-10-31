from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Text, Uuid
from sqlalchemy.orm import relationship

from app.database import Base


class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(Uuid, primary_key=True, default=uuid4, index=True)
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    note_id = Column(
        Uuid, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    note = relationship("Note", back_populates="flashcards")
