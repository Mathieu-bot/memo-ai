from pydantic import BaseModel, ConfigDict


class CourseBase(BaseModel):
    title: str
    description: str | None = None


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None


class CourseInDBBase(CourseBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class Course(CourseInDBBase):
    pass
