from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.schemas.quiz import Quiz, QuizCreate, QuizUpdate, QuizWithQuestions
from app.services.db import get_db
from app.models.quiz import Quiz as QuizModel
from app.models.course import Course as CourseModel

router = APIRouter(prefix="/quizzes", tags=["quizzes"])

@router.get("/", response_model=List[Quiz])
def get_quizzes(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    quizzes = db.query(QuizModel).offset(skip).limit(limit).all()
    return quizzes

@router.post("/", response_model=Quiz, status_code=status.HTTP_201_CREATED)
def create_quiz(quiz: QuizCreate, db: Session = Depends(get_db)):
    course = db.query(CourseModel).filter(CourseModel.id == quiz.course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    db_quiz = QuizModel(
        title=quiz.title,
        description=quiz.description,
        course_id=quiz.course_id
    )
    db.add(db_quiz)
    db.commit()
    db.refresh(db_quiz)
    return db_quiz

@router.get("/{quiz_id}", response_model=QuizWithQuestions)
def get_quiz(quiz_id: int, db: Session = Depends(get_db)):
    quiz = db.query(QuizModel).filter(QuizModel.id == quiz_id).first()
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz

@router.put("/{quiz_id}", response_model=Quiz)
def update_quiz(quiz_id: int, quiz: QuizUpdate, db: Session = Depends(get_db)):
    db_quiz = db.query(QuizModel).filter(QuizModel.id == quiz_id).first()
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Si course_id est modifié, vérifier que le nouveau cours existe
    if quiz.course_id is not None and quiz.course_id != db_quiz.course_id:
        course = db.query(CourseModel).filter(CourseModel.id == quiz.course_id).first()
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")

    update_data = quiz.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_quiz, key, value)

    db.commit()
    db.refresh(db_quiz)
    return db_quiz

@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quiz(quiz_id: int, db: Session = Depends(get_db)):
    db_quiz = db.query(QuizModel).filter(QuizModel.id == quiz_id).first()
    if db_quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")

    db.delete(db_quiz)
    db.commit()
    return None