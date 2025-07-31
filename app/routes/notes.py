from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional

from app.schemas.note import Note, NoteCreate, NoteUpdate, NoteWithSummary
from app.services.db import get_db
from app.services.ai_service import AIService
from app.models.note import Note as NoteModel
from app.models.course import Course as CourseModel

router = APIRouter(prefix="/notes", tags=["notes"])

@router.get("/", response_model=List[Note])
def get_notes(
    skip: int = 0, 
    limit: int = 100, 
    title: Optional[str] = None,
    course_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    ## Get all notes with options of filtering.
    query = db.query(NoteModel)
    if title:
        query = query.filter(NoteModel.title.contains(title))
    if course_id:
        query = query.filter(NoteModel.course_id == course_id)
    notes = query.offset(skip).limit(limit).all()
    return notes

@router.post("/", response_model=Note, status_code=status.HTTP_201_CREATED)
def create_note(note: NoteCreate, generate_summary: bool = True, db: Session = Depends(get_db)):
    course = db.query(CourseModel).filter(CourseModel.id == note.course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    db_note = NoteModel(**note.dict())
    db.add(db_note)
    db.flush()

    if generate_summary:
        summary = AIService.generate_summary(note.content)
        db_note.summary = summary

    db.commit()
    db.refresh(db_note)
    return db_note

@router.get("/{note_id}", response_model=NoteWithSummary)
def get_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(NoteModel).filter(NoteModel.id == note_id).first()
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note

@router.put("/{note_id}", response_model=Note)
def update_note(note_id: int, note: NoteUpdate, regenerate_summary: bool = False, db: Session = Depends(get_db)):
    db_note = db.query(NoteModel).filter(NoteModel.id == note_id).first()
    if db_note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    if note.course_id is not None and note.course_id != db_note.course_id:
        course = db.query(CourseModel).filter(CourseModel.id == note.course_id).first()
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")

    update_data = note.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_note, key, value)

    if regenerate_summary or 'content' in update_data:
        db_note.summary = AIService.generate_summary(db_note.content)

    db.commit()
    db.refresh(db_note)
    return db_note

@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    db_note = db.query(NoteModel).filter(NoteModel.id == note_id).first()
    if db_note is None:
        raise HTTPException(status_code=404, detail="Note not found")

    db.delete(db_note)
    db.commit()
    return None

@router.post("/{note_id}/regenerate-summary", response_model=Note)
def regenerate_summary(note_id: int, db: Session = Depends(get_db)):
    db_note = db.query(NoteModel).filter(NoteModel.id == note_id).first()
    if db_note is None:
        raise HTTPException(status_code=404, detail="Note not found")

    db_note.summary = AIService.generate_summary(db_note.content)

    db.commit()
    db.refresh(db_note)
    return db_note

@router.post("/{note_id}/generate-flashcards", status_code=status.HTTP_200_OK)
def generate_flashcards(note_id: int, num_cards: int = 10, db: Session = Depends(get_db)):
    db_note = db.query(NoteModel).filter(NoteModel.id == note_id).first()
    if db_note is None:
        raise HTTPException(status_code=404, detail="Note not found")

    flashcards = AIService.generate_flashcards(db_note.content, num_cards)

    return {
        "note_id": note_id,
        "flashcards": flashcards
    }
