from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import get_course_or_404, list_accessible_courses
from app.auth import current_user
from app.dependencies import get_db
from app.exceptions import NotFoundError
from app.models import Course as CourseModel
from app.models import CourseMember as CourseMemberModel
from app.models import User
from app.models.course_member import ROLE_MEMBER, ROLE_OWNER
from app.schemas import (
    Course,
    CourseCreate,
    CourseMember,
    CourseMemberCreate,
    CourseUpdate,
)

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/", response_model=list[Course])
async def get_courses(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    skip: int = 0,
    limit: int = 100,
):
    return await list_accessible_courses(db, user, skip, limit)


@router.post("/", response_model=Course, status_code=status.HTTP_201_CREATED)
async def create_course(
    course: CourseCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    db_course = CourseModel(**course.model_dump(), owner_id=user.id)
    db.add(db_course)
    await db.commit()
    await db.refresh(db_course)
    return db_course


@router.get("/{course_id}", response_model=Course)
async def get_course(
    course_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    return await get_course_or_404(db, user, course_id)


@router.put("/{course_id}", response_model=Course)
async def update_course(
    course_id: UUID,
    course: CourseUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    db_course = await get_course_or_404(db, user, course_id, write=True)

    update_data = course.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_course, key, value)

    await db.commit()
    await db.refresh(db_course)
    return db_course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    db_course = await get_course_or_404(db, user, course_id, write=True)

    await db.delete(db_course)
    await db.commit()
    return None


@router.get("/{course_id}/members", response_model=list[CourseMember])
async def list_course_members(
    course_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    db_course = await get_course_or_404(db, user, course_id, write=True)

    result = await db.execute(
        select(CourseMemberModel).where(CourseMemberModel.course_id == course_id)
    )
    members = [
        CourseMember(
            course_id=db_course.id, user_id=db_course.owner_id, role=ROLE_OWNER
        )
    ]
    members.extend(CourseMember.model_validate(m) for m in result.scalars().all())
    return members


@router.post(
    "/{course_id}/members",
    response_model=CourseMember,
    status_code=status.HTTP_201_CREATED,
)
async def add_course_member(
    course_id: UUID,
    member: CourseMemberCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    db_course = await get_course_or_404(db, user, course_id, write=True)

    if member.user_id == db_course.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot share a course with its owner",
        )

    existing = await db.execute(
        select(CourseMemberModel).where(
            CourseMemberModel.course_id == course_id,
            CourseMemberModel.user_id == member.user_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this course",
        )

    target = await db.execute(select(User).where(User.id == member.user_id))
    if target.scalar_one_or_none() is None:
        raise NotFoundError("User", member.user_id)

    db_member = CourseMemberModel(
        course_id=course_id, user_id=member.user_id, role=ROLE_MEMBER
    )
    db.add(db_member)
    await db.commit()
    await db.refresh(db_member)
    return db_member


@router.delete("/{course_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_course_member(
    course_id: UUID,
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    await get_course_or_404(db, user, course_id, write=True)

    result = await db.execute(
        select(CourseMemberModel).where(
            CourseMemberModel.course_id == course_id,
            CourseMemberModel.user_id == user_id,
        )
    )
    db_member = result.scalar_one_or_none()
    if db_member is None:
        raise NotFoundError("CourseMember", f"{course_id}:{user_id}")

    await db.delete(db_member)
    await db.commit()
    return None
