from uuid import UUID

from fastapi_users import schemas as users_schemas


class UserRead(users_schemas.BaseUser[UUID]):
    username: str


class UserCreate(users_schemas.BaseUserCreate):
    username: str


class UserUpdate(users_schemas.BaseUserUpdate):
    username: str | None = None
