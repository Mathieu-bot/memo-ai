import uuid
from typing import TYPE_CHECKING

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    _UserBase = SQLAlchemyBaseUserTable[uuid.UUID]
else:
    _UserBase = SQLAlchemyBaseUserTable


class User(_UserBase, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)

    owned_courses = relationship(
        "Course",
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    memberships = relationship(
        "CourseMember",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
