import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, IntegerIDMixin, exceptions
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_db
from app.models import User

logger = logging.getLogger(__name__)
settings = get_settings()


class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = settings.JWT_SECRET
    verification_token_secret = settings.JWT_SECRET

    async def create(
        self,
        user_create,
        safe: bool = False,
        request: Request | None = None,
    ) -> User:
        """Create a user, additionally enforcing a unique username."""
        result = await self.user_db.session.execute(
            select(User).where(User.username == user_create.username)
        )
        if result.first() is not None:
            raise exceptions.UserAlreadyExists()
        return await super().create(user_create, safe=safe, request=request)

    async def on_after_register(self, user: User, request: Request | None = None):
        logger.info("User %s successfully registered", user.email)

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ):
        logger.info(
            "Verification token for %s (in production, email it): %s",
            user.email,
            token,
        )

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ):
        logger.info(
            "Password reset token for %s (in production, email it): %s",
            user.email,
            token,
        )


async def get_user_db(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(
    user_db: Annotated[SQLAlchemyUserDatabase, Depends(get_user_db)],
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.JWT_SECRET,
        lifetime_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, int](get_user_manager, [auth_backend])

current_user = fastapi_users.current_user(active=True, verified=True)
