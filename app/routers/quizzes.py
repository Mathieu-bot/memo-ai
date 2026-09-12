from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.access import (
    course_owned_condition,
    course_readable_condition,
    get_course_or_404,
)
from app.auth import current_user
from app.dependencies import get_db
from app.exceptions import NotFoundError
from app.models import Course as CourseModel
from app.models import Quiz as QuizModel
from app.models import User
from app.schemas import Quiz, QuizCreate, QuizUpdate, QuizWithQuestions

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


@router.get("/", response_model=list[Quiz])
async def get_quizzes(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
):
    statement = (
        select(QuizModel)
        .join(CourseModel, QuizModel.course_id == CourseModel.id)
        .where(course_readable_condition(user.id))
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(statement)
    return result.scalars().all()


@router.post("/", response_model=Quiz, status_code=status.HTTP_201_CREATED)
async def create_quiz(
    quiz: QuizCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    await get_course_or_404(db, user, quiz.course_id, write=True)

    db_quiz = QuizModel(**quiz.model_dump())
    db.add(db_quiz)
    await db.commit()
    await db.refresh(db_quiz)
    return db_quiz


@router.get("/{quiz_id}", response_model=QuizWithQuestions)
async def get_quiz(
    quiz_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    statement = (
        select(QuizModel)
        .options(selectinload(QuizModel.questions))
        .join(CourseModel, QuizModel.course_id == CourseModel.id)
        .where(QuizModel.id == quiz_id, course_readable_condition(user.id))
    )
    quiz = (await db.execute(statement)).scalar_one_or_none()
    if quiz is None:
        raise NotFoundError("Quiz", quiz_id)
    return quiz


@router.put("/{quiz_id}", response_model=Quiz)
async def update_quiz(
    quiz_id: UUID,
    quiz: QuizUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    statement = (
        select(QuizModel)
        .join(CourseModel, QuizModel.course_id == CourseModel.id)
        .where(QuizModel.id == quiz_id, course_owned_condition(user.id))
    )
    db_quiz = (await db.execute(statement)).scalar_one_or_none()
    if db_quiz is None:
        raise NotFoundError("Quiz", quiz_id)

    if quiz.course_id is not None and quiz.course_id != db_quiz.course_id:
        await get_course_or_404(db, user, quiz.course_id, write=True)

    update_data = quiz.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_quiz, key, value)

    await db.commit()
    await db.refresh(db_quiz)
    return db_quiz


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz(
    quiz_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    statement = (
        select(QuizModel)
        .join(CourseModel, QuizModel.course_id == CourseModel.id)
        .where(QuizModel.id == quiz_id, course_owned_condition(user.id))
    )
    db_quiz = (await db.execute(statement)).scalar_one_or_none()
    if db_quiz is None:
        raise NotFoundError("Quiz", quiz_id)

    await db.delete(db_quiz)
    await db.commit()
    return None
