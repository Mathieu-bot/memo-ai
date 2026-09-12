from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CourseBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None

    @field_validator("title")
    @classmethod
    def _reject_null_title(cls, value):
        if value is None:
            raise ValueError("title must not be null; omit it instead")
        return value


class CourseInDBBase(CourseBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class Course(CourseInDBBase):
    pass
