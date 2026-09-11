from uuid import UUID

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.models import Course as CourseModel
from app.models import CourseMember as CourseMemberModel
from app.models import User


def course_owned_condition(user_id: UUID):
    """Courses owned directly by the user."""
    return CourseModel.owner_id == user_id


def course_shared_condition(user_id: UUID):
    """Courses shared with the user via a membership."""
    return exists().where(
        and_(
            CourseMemberModel.course_id == CourseModel.id,
            CourseMemberModel.user_id == user_id,
        )
    )


def course_readable_condition(user_id: UUID):
    """Courses the user can read: owned or shared."""
    return or_(course_owned_condition(user_id), course_shared_condition(user_id))


async def get_course_or_404(
    db: AsyncSession, user: User, course_id: UUID, *, write: bool = False
) -> CourseModel:
    """Fetch a course the user may access. 404 for anything else (neutral)."""
    condition = (
        course_owned_condition(user.id) if write else course_readable_condition(user.id)
    )
    statement = select(CourseModel).where(CourseModel.id == course_id, condition)
    course = (await db.execute(statement)).scalar_one_or_none()
    if course is None:
        raise NotFoundError("Course", course_id)
    return course


async def list_accessible_courses(
    db: AsyncSession, user: User, skip: int = 0, limit: int = 100
) -> list[CourseModel]:
    statement = (
        select(CourseModel)
        .where(course_readable_condition(user.id))
        .offset(skip)
        .limit(limit)
    )
    return (await db.execute(statement)).scalars().all()
