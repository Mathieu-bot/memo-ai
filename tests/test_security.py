import asyncio
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update as sa_update

import app.main as main_module
from app.dependencies import get_db
from app.models import User
from app.utils.ratelimit import FixedWindowRateLimiter
from tests.conftest import TestingSessionLocal, override_get_db

MISSING_ID = "00000000-0000-0000-0000-000000000000"


def _make_client() -> TestClient:
    app = main_module.create_app()
    # Fresh apps must reuse the shared test DB like the `client` fixture does.
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app, raise_server_exceptions=False)


def _enable_rate_limiting(monkeypatch):
    monkeypatch.setattr(main_module.settings, "RATE_LIMITING_ENABLED", True)
    monkeypatch.setattr(main_module.limiter, "enabled", True)


def _verify_in_db(user_id: UUID) -> None:
    async def _go():
        async with TestingSessionLocal() as session:
            await session.execute(
                sa_update(User).where(User.id == user_id).values(is_verified=True)
            )
            await session.commit()

    asyncio.run(_go())


def test_fixed_window_limiter_blocks_bursts():
    limiter = FixedWindowRateLimiter("3/minute")
    assert [limiter.allow("1.2.3.4") for _ in range(3)] == [True, True, True]
    assert limiter.allow("1.2.3.4") is False
    assert limiter.allow("4.5.6.7") is True  # other key unaffected


def test_auth_login_is_rate_limited(monkeypatch):
    _enable_rate_limiting(monkeypatch)
    monkeypatch.setattr(main_module.settings, "RATE_LIMIT_AUTH", "3/minute")

    client = _make_client()
    statuses = [
        client.post(
            "/auth/login",
            data={"username": "user@example.com", "password": "wrong"},
        ).status_code
        for _ in range(5)
    ]
    assert statuses[0] != 429  # allowed, bad credentials
    assert statuses[3] == 429
    assert statuses[4] == 429


def test_slowapi_route_is_rate_limited(monkeypatch):
    _enable_rate_limiting(monkeypatch)

    client = _make_client()
    register = client.post(
        "/auth/register",
        json={
            "email": "rl@example.com",
            "password": "password123",
            "username": "ratelimit",
        },
    )
    assert register.status_code == 201, register.text
    _verify_in_db(UUID(register.json()["id"]))

    login = client.post(
        "/auth/login", data={"username": "rl@example.com", "password": "password123"}
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    statuses = [
        client.post(
            "/videos/upload",
            data={"title": "V", "course_id": MISSING_ID},
            files={"file": ("v.mp4", b"tiny", "video/mp4")},
            headers=headers,
        ).status_code
        for _ in range(12)
    ]
    assert statuses[:10] == [404] * 10  # allowed, course not found
    assert statuses[10] == 429
    assert statuses[11] == 429


def test_production_startup_requires_email_settings(monkeypatch):
    monkeypatch.setattr(main_module.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(main_module.settings, "RESEND_API_KEY", "")
    monkeypatch.setattr(main_module.settings, "PUBLIC_BASE_URL", "")
    with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL"):
        main_module.create_app()
