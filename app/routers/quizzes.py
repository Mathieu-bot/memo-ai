from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.exceptions import NotFoundError
from app.models import Course as CourseModel
from app.models import Quiz as QuizModel
from app.schemas import Quiz, QuizCreate, QuizUpdate, QuizWithQuestions

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


@router.get("/", response_model=list[Quiz])
def get_quizzes(
    db: Annotated[Session, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
):
    return db.query(QuizModel).offset(skip).limit(limit).all()


@router.post("/", response_model=Quiz, status_code=status.HTTP_201_CREATED)
def create_quiz(quiz: QuizCreate, db: Annotated[Session, Depends(get_db)]):
    course = db.query(CourseModel).filter(CourseModel.id == quiz.course_id).first()
    if course is None:
        raise NotFoundError("Course", quiz.course_id)

    db_quiz = QuizModel(**quiz.model_dump())
    db.add(db_quiz)
    db.commit()
    db.refresh(db_quiz)
    return db_quiz


@router.get("/{quiz_id}", response_model=QuizWithQuestions)
def get_quiz(quiz_id: int, db: Annotated[Session, Depends(get_db)]):
    quiz = db.query(QuizModel).filter(QuizModel.id == quiz_id).first()
    if quiz is None:
        raise NotFoundError("Quiz", quiz_id)
    return quiz


@router.put("/{quiz_id}", response_model=Quiz)
def update_quiz(
    quiz_id: int, quiz: QuizUpdate, db: Annotated[Session, Depends(get_db)]
):
    db_quiz = db.query(QuizModel).filter(QuizModel.id == quiz_id).first()
    if db_quiz is None:
        raise NotFoundError("Quiz", quiz_id)

    if quiz.course_id is not None and quiz.course_id != db_quiz.course_id:
        course = db.query(CourseModel).filter(CourseModel.id == quiz.course_id).first()
        if course is None:
            raise NotFoundError("Course", quiz.course_id)

    update_data = quiz.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_quiz, key, value)

    db.commit()
    db.refresh(db_quiz)
    return db_quiz


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quiz(quiz_id: int, db: Annotated[Session, Depends(get_db)]):
    db_quiz = db.query(QuizModel).filter(QuizModel.id == quiz_id).first()
    if db_quiz is None:
        raise NotFoundError("Quiz", quiz_id)

    db.delete(db_quiz)
    db.commit()
    return None
