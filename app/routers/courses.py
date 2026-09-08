from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.exceptions import NotFoundError
from app.models import Course as CourseModel
from app.schemas import Course, CourseCreate, CourseUpdate

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/", response_model=list[Course])
def get_courses(
    db: Annotated[Session, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
):
    return db.query(CourseModel).offset(skip).limit(limit).all()


@router.post("/", response_model=Course, status_code=status.HTTP_201_CREATED)
def create_course(course: CourseCreate, db: Annotated[Session, Depends(get_db)]):
    db_course = CourseModel(**course.model_dump())
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course


@router.get("/{course_id}", response_model=Course)
def get_course(course_id: int, db: Annotated[Session, Depends(get_db)]):
    course = db.query(CourseModel).filter(CourseModel.id == course_id).first()
    if course is None:
        raise NotFoundError("Course", course_id)
    return course


@router.put("/{course_id}", response_model=Course)
def update_course(
    course_id: int, course: CourseUpdate, db: Annotated[Session, Depends(get_db)]
):
    db_course = db.query(CourseModel).filter(CourseModel.id == course_id).first()
    if db_course is None:
        raise NotFoundError("Course", course_id)

    update_data = course.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_course, key, value)

    db.commit()
    db.refresh(db_course)
    return db_course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: int, db: Annotated[Session, Depends(get_db)]):
    db_course = db.query(CourseModel).filter(CourseModel.id == course_id).first()
    if db_course is None:
        raise NotFoundError("Course", course_id)

    db.delete(db_course)
    db.commit()
    return None
