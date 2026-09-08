from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.exceptions import AIServiceError, NotFoundError
from app.models import Course as CourseModel
from app.models import Note as NoteModel
from app.schemas import Note, NoteCreate, NoteUpdate, NoteWithSummary
from app.services.ai import FlashcardService, SummaryService, get_ai_provider

router = APIRouter(prefix="/notes", tags=["notes"])


def _get_note_or_404(note_id: int, db: Session) -> NoteModel:
    note = db.query(NoteModel).filter(NoteModel.id == note_id).first()
    if note is None:
        raise NotFoundError("Note", note_id)
    return note


def _get_course_or_404(course_id: int, db: Session) -> CourseModel:
    course = db.query(CourseModel).filter(CourseModel.id == course_id).first()
    if course is None:
        raise NotFoundError("Course", course_id)
    return course


async def _generate_summary(content: str) -> str:
    provider = get_ai_provider()
    summary_service = SummaryService(provider)
    return await summary_service.summarize(content)


@router.get("/", response_model=list[Note])
def get_notes(
    db: Annotated[Session, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
    title: str | None = None,
    course_id: int | None = None,
):
    query = db.query(NoteModel)
    if title:
        query = query.filter(NoteModel.title.contains(title))
    if course_id:
        query = query.filter(NoteModel.course_id == course_id)
    return query.offset(skip).limit(limit).all()


@router.post("/", response_model=Note, status_code=status.HTTP_201_CREATED)
async def create_note(
    note: NoteCreate,
    db: Annotated[Session, Depends(get_db)],
    generate_summary: bool = True,
):
    _get_course_or_404(note.course_id, db)

    db_note = NoteModel(**note.model_dump())
    db.add(db_note)
    db.flush()

    if generate_summary:
        try:
            db_note.summary = await _generate_summary(note.content)
        except AIServiceError:
            db_note.summary = None

    db.commit()
    db.refresh(db_note)
    return db_note


@router.get("/{note_id}", response_model=NoteWithSummary)
def get_note(note_id: int, db: Annotated[Session, Depends(get_db)]):
    return _get_note_or_404(note_id, db)


@router.put("/{note_id}", response_model=Note)
async def update_note(
    note_id: int,
    note: NoteUpdate,
    db: Annotated[Session, Depends(get_db)],
    regenerate_summary: bool = False,
):
    db_note = _get_note_or_404(note_id, db)

    if note.course_id is not None and note.course_id != db_note.course_id:
        _get_course_or_404(note.course_id, db)

    update_data = note.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_note, key, value)

    if regenerate_summary or "content" in update_data:
        try:
            db_note.summary = await _generate_summary(db_note.content)
        except AIServiceError:
            db_note.summary = None

    db.commit()
    db.refresh(db_note)
    return db_note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, db: Annotated[Session, Depends(get_db)]):
    db_note = _get_note_or_404(note_id, db)
    db.delete(db_note)
    db.commit()
    return None


@router.post("/{note_id}/summarize", response_model=Note)
async def summarize_note(note_id: int, db: Annotated[Session, Depends(get_db)]):
    db_note = _get_note_or_404(note_id, db)

    try:
        db_note.summary = await _generate_summary(db_note.content)
    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI summarization failed",
        ) from exc

    db.commit()
    db.refresh(db_note)
    return db_note


@router.post("/{note_id}/generate-flashcards", status_code=status.HTTP_200_OK)
async def generate_flashcards(
    note_id: int,
    db: Annotated[Session, Depends(get_db)],
    num_cards: int = 10,
):
    db_note = _get_note_or_404(note_id, db)

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
