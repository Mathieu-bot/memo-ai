from pydantic import BaseModel
from typing import Optional

class CourseBase(BaseModel) :
    title: str
    description: Optional[str] = None

class CourseCreate(CourseBase) :
    pass

class CourseUpdate(CourseBase) :
    pass

class CourseInDBBase(CourseBase) :
    id: int

    class Config :
        orm_mode = True  # pour pouvoir retourner un modèle SQLAlchemy directement

class Course(CourseInDBBase) :
    pass