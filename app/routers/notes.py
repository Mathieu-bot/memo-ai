from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import (
    course_owned_condition,
    course_readable_condition,
    get_course_or_404,
)
from app.auth import current_user
from app.dependencies import get_db
from app.exceptions import AIServiceError, NotFoundError
from app.models import Course as CourseModel
from app.models import Note as NoteModel
from app.models import User
from app.schemas import Note, NoteCreate, NoteUpdate, NoteWithSummary
from app.services.ai import FlashcardService, SummaryService, get_ai_provider

router = APIRouter(prefix="/notes", tags=["notes"])


async def _get_accessible_note_or_404(
    note_id: UUID, user: User, db: AsyncSession
) -> NoteModel:
    statement = (
        select(NoteModel)
        .join(CourseModel, NoteModel.course_id == CourseModel.id)
        .where(NoteModel.id == note_id, course_readable_condition(user.id))
    )
    note = (await db.execute(statement)).scalar_one_or_none()
    if note is None:
        raise NotFoundError("Note", note_id)
    return note


async def _get_owned_note_or_404(
    note_id: UUID, user: User, db: AsyncSession
) -> NoteModel:
    statement = (
        select(NoteModel)
        .join(CourseModel, NoteModel.course_id == CourseModel.id)
        .where(NoteModel.id == note_id, course_owned_condition(user.id))
    )
    note = (await db.execute(statement)).scalar_one_or_none()
    if note is None:
        raise NotFoundError("Note", note_id)
    return note


async def _generate_summary(content: str) -> str:
    provider = get_ai_provider()
    summary_service = SummaryService(provider)
    return await summary_service.summarize(content)


@router.get("/", response_model=list[Note])
async def get_notes(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    skip: int = 0,
    limit: int = 100,
    title: str | None = None,
    course_id: UUID | None = None,
):
    statement = (
        select(NoteModel)
        .join(CourseModel, NoteModel.course_id == CourseModel.id)
        .where(course_readable_condition(user.id))
    )
    if title:
        statement = statement.where(NoteModel.title.contains(title))
    if course_id:
        statement = statement.where(NoteModel.course_id == course_id)
    statement = statement.offset(skip).limit(limit)
    result = await db.execute(statement)
    return result.scalars().all()


@router.post("/", response_model=Note, status_code=status.HTTP_201_CREATED)
async def create_note(
    note: NoteCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    generate_summary: bool = True,
):
    await get_course_or_404(db, user, note.course_id, write=True)

    db_note = NoteModel(**note.model_dump())
    db.add(db_note)
    await db.flush()

    if generate_summary:
        try:
            db_note.summary = await _generate_summary(note.content)
        except AIServiceError:
            db_note.summary = None

    await db.commit()
    await db.refresh(db_note)
    return db_note


@router.get("/{note_id}", response_model=NoteWithSummary)
async def get_note(
    note_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    return await _get_accessible_note_or_404(note_id, user, db)


@router.put("/{note_id}", response_model=Note)
async def update_note(
    note_id: UUID,
    note: NoteUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    regenerate_summary: bool = False,
):
    db_note = await _get_owned_note_or_404(note_id, user, db)

    if note.course_id is not None and note.course_id != db_note.course_id:
        await get_course_or_404(db, user, note.course_id, write=True)

    update_data = note.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_note, key, value)

    if regenerate_summary or "content" in update_data:
        try:
            db_note.summary = await _generate_summary(db_note.content)
        except AIServiceError:
            db_note.summary = None

    await db.commit()
    await db.refresh(db_note)
    return db_note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    db_note = await _get_owned_note_or_404(note_id, user, db)
    await db.delete(db_note)
    await db.commit()
    return None


@router.post("/{note_id}/summarize", response_model=Note)
async def summarize_note(
    note_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    db_note = await _get_owned_note_or_404(note_id, user, db)

    try:
        db_note.summary = await _generate_summary(db_note.content)
    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI summarization failed",
        ) from exc

    await db.commit()
    await db.refresh(db_note)
    return db_note


@router.post("/{note_id}/generate-flashcards", status_code=status.HTTP_200_OK)
async def generate_flashcards(
    note_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    num_cards: int = 10,
):
    db_note = await _get_accessible_note_or_404(note_id, user, db)

    provider = get_ai_provider()
    flashcard_service = FlashcardService(provider)
    try:
        flashcards = await flashcard_service.generate(db_note.content, num_cards)
    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI flashcard generation failed",
        ) from exc

    return {"note_id": note_id, "flashcards": flashcards}
