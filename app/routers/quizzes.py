from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db
from app.exceptions import NotFoundError
from app.models import Course as CourseModel
from app.models import Quiz as QuizModel
from app.schemas import Quiz, QuizCreate, QuizUpdate, QuizWithQuestions

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


@router.get("/", response_model=list[Quiz])
async def get_quizzes(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
):
    result = await db.execute(select(QuizModel).offset(skip).limit(limit))
    return result.scalars().all()


@router.post("/", response_model=Quiz, status_code=status.HTTP_201_CREATED)
async def create_quiz(quiz: QuizCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    course_result = await db.execute(
        select(CourseModel).where(CourseModel.id == quiz.course_id)
    )
    if course_result.scalar_one_or_none() is None:
        raise NotFoundError("Course", quiz.course_id)

    db_quiz = QuizModel(**quiz.model_dump())
    db.add(db_quiz)
    await db.commit()
    await db.refresh(db_quiz)
    return db_quiz


@router.get("/{quiz_id}", response_model=QuizWithQuestions)
async def get_quiz(quiz_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(QuizModel)
        .options(selectinload(QuizModel.questions))
        .where(QuizModel.id == quiz_id)
    )
    quiz = result.scalar_one_or_none()
    if quiz is None:
        raise NotFoundError("Quiz", quiz_id)
    return quiz


@router.put("/{quiz_id}", response_model=Quiz)
async def update_quiz(
    quiz_id: int, quiz: QuizUpdate, db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(select(QuizModel).where(QuizModel.id == quiz_id))
    db_quiz = result.scalar_one_or_none()
    if db_quiz is None:
        raise NotFoundError("Quiz", quiz_id)

    if quiz.course_id is not None and quiz.course_id != db_quiz.course_id:
        course_result = await db.execute(
            select(CourseModel).where(CourseModel.id == quiz.course_id)
        )
        if course_result.scalar_one_or_none() is None:
            raise NotFoundError("Course", quiz.course_id)

    update_data = quiz.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_quiz, key, value)

    await db.commit()
    await db.refresh(db_quiz)
    return db_quiz


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz(quiz_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(QuizModel).where(QuizModel.id == quiz_id))
    db_quiz = result.scalar_one_or_none()
    if db_quiz is None:
        raise NotFoundError("Quiz", quiz_id)

    await db.delete(db_quiz)
    await db.commit()
    return None
