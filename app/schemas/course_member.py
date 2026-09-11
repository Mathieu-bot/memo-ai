from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CourseMemberCreate(BaseModel):
    user_id: UUID


class CourseMemberInDBBase(BaseModel):
    course_id: UUID
    user_id: UUID
    role: str
    model_config = ConfigDict(from_attributes=True)


class CourseMember(CourseMemberInDBBase):
    pass
