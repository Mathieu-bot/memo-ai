from sqlalchemy import Column, ForeignKey, String, Uuid
from sqlalchemy.orm import relationship

from app.database import Base

ROLE_OWNER = "owner"
ROLE_MEMBER = "member"
VALID_ROLES = (ROLE_OWNER, ROLE_MEMBER)


class CourseMember(Base):
    __tablename__ = "course_members"

    course_id = Column(
        Uuid, ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True
    )
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role = Column(String(20), nullable=False, default=ROLE_MEMBER)

    course = relationship("Course", back_populates="members")
    user = relationship("User", back_populates="memberships")
