from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.exceptions import NotFoundError
from app.models import Course as CourseModel
from app.schemas import Course, CourseCreate, CourseUpdate

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/", response_model=list[Course])
async def get_courses(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
):
    result = await db.execute(select(CourseModel).offset(skip).limit(limit))
    return result.scalars().all()


@router.post("/", response_model=Course, status_code=status.HTTP_201_CREATED)
async def create_course(
    course: CourseCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    db_course = CourseModel(**course.model_dump())
    db.add(db_course)
    await db.commit()
    await db.refresh(db_course)
    return db_course


@router.get("/{course_id}", response_model=Course)
async def get_course(course_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(CourseModel).where(CourseModel.id == course_id))
    course = result.scalar_one_or_none()
    if course is None:
        raise NotFoundError("Course", course_id)
    return course


@router.put("/{course_id}", response_model=Course)
async def update_course(
    course_id: int, course: CourseUpdate, db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(select(CourseModel).where(CourseModel.id == course_id))
    db_course = result.scalar_one_or_none()
    if db_course is None:
        raise NotFoundError("Course", course_id)

    update_data = course.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_course, key, value)

    await db.commit()
    await db.refresh(db_course)
    return db_course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(course_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(CourseModel).where(CourseModel.id == course_id))
    db_course = result.scalar_one_or_none()
    if db_course is None:
        raise NotFoundError("Course", course_id)

    await db.delete(db_course)
    await db.commit()
    return None
