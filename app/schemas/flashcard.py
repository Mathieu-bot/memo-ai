from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Flashcard(BaseModel):
    id: UUID
    front: str
    back: str
    note_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FlashcardBatch(BaseModel):
    note_id: UUID
    flashcards: list[Flashcard]
