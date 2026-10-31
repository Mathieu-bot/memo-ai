"""Gather the study material of a course so AI features can be grounded on it."""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Note as NoteModel
from app.models import Video as VideoModel

logger = logging.getLogger(__name__)

# Keeps the prompt within a comfortable budget for free-tier models.
MAX_MATERIAL_CHARS = 60_000


async def collect_course_material(
    db: AsyncSession,
    course_id: UUID,
    description: str | None = None,
    max_chars: int = MAX_MATERIAL_CHARS,
) -> str:
    """Return the course description, notes and video transcripts as one text.

    Sections are ordered oldest first and the result is truncated to
    ``max_chars``. An empty string means the course has nothing to study yet.
    """
    sections: list[str] = []
    if description and description.strip():
        sections.append(f"## Course description\n{description.strip()}")

    notes = await db.execute(
        select(NoteModel)
        .where(NoteModel.course_id == course_id)
        .order_by(NoteModel.created_at)
    )
    for note in notes.scalars():
        if note.content and note.content.strip():
            sections.append(f"## Note: {note.title}\n{note.content.strip()}")

    videos = await db.execute(
        select(VideoModel)
        .where(VideoModel.course_id == course_id)
        .order_by(VideoModel.created_at)
    )
    for video in videos.scalars():
        if video.transcript and video.transcript.strip():
            sections.append(
                f"## Video transcript: {video.title}\n{video.transcript.strip()}"
            )

    material = "\n\n".join(sections)
    if len(material) > max_chars:
        logger.info(
            "Course %s material truncated from %d to %d chars",
            course_id,
            len(material),
            max_chars,
        )
        material = material[:max_chars]
    return material
