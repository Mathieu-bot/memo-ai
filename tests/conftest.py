import asyncio
import os
import tempfile
from uuid import UUID, uuid4

os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.database import Base
from app.dependencies import get_db
from app.models import User

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

TEST_ENGINE = create_async_engine(f"sqlite+aiosqlite:///{_tmp_db.name}")
TestingSessionLocal = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)


async def _init_tables():
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


asyncio.run(_init_tables())


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
def client():
    from app.main import app

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client(client):
    """Authenticated client with a verified user."""
    response = client.post(
        "/auth/register",
        json={
            "email": "user@example.com",
            "password": "password123",
            "username": "alice",
        },
    )
    assert response.status_code == 201, response.text
    user_id = UUID(response.json()["id"])

    async def _verify():
        from sqlalchemy import update

        async with TestingSessionLocal() as session:
            await session.execute(
                update(User).where(User.id == user_id).values(is_verified=True)
            )
            await session.commit()

    asyncio.run(_verify())

    login = client.post(
        "/auth/login",
        data={"username": "user@example.com", "password": "password123"},
    )
    assert login.status_code == 200, login.text
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    return client


def _db_user(email="direct@example.com", username="direct") -> User:
    """Insert a verified user directly (for in-process handler calls)."""

    async def _go():
        async with TestingSessionLocal() as session:
            user = User(
                id=uuid4(),
                email=email,
                username=username,
                hashed_password="not-used",
                is_active=True,
                is_verified=True,
                is_superuser=False,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    return asyncio.run(_go())


@pytest.fixture(autouse=True)
def clean_db():
    yield

    async def _clean():
        async with TestingSessionLocal() as session:
            await session.execute(text("DELETE FROM answers"))
            await session.execute(text("DELETE FROM questions"))
            await session.execute(text("DELETE FROM quizzes"))
            await session.execute(text("DELETE FROM videos"))
            await session.execute(text("DELETE FROM notes"))
            await session.execute(text("DELETE FROM course_members"))
            await session.execute(text("DELETE FROM courses"))
            await session.execute(text("DELETE FROM users"))
            await session.commit()

    asyncio.run(_clean())
