import asyncio
import logging
from types import SimpleNamespace

import httpx

from app.services import email_service


def _settings(**overrides):
    base = {
        "PUBLIC_BASE_URL": "https://memoai.example.com",
        "RESEND_API_KEY": "",
        "EMAIL_FROM": "noreply@memoai.example.com",
        "is_production": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_build_url_strips_trailing_slash(monkeypatch):
    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: _settings(PUBLIC_BASE_URL="https://x.com/"),
    )
    assert (
        email_service._build_url("/auth/verify", "tok")
        == "https://x.com/auth/verify?token=tok"
    )


def test_send_verification_email_logs_in_dev_without_key(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(email_service, "get_settings", lambda: _settings())
    asyncio.run(email_service.send_verification_email("a@b.com", "tok"))
    assert "[dev] Email to a@b.com" in caplog.text
    assert "auth/verify?token=tok" in caplog.text


def test_send_password_reset_email_logs_in_dev_without_key(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(email_service, "get_settings", lambda: _settings())
    asyncio.run(email_service.send_password_reset_email("a@b.com", "tok"))
    assert "[dev] Email to a@b.com" in caplog.text
    assert "auth/reset-password?token=tok" in caplog.text


def test_send_email_in_production_without_key_logs_error(monkeypatch, caplog):
    monkeypatch.setattr(
        email_service, "get_settings", lambda: _settings(is_production=True)
    )
    asyncio.run(email_service.send_verification_email("a@b.com", "tok"))
    assert "RESEND_API_KEY is missing" in caplog.text


class _FakeResendClient:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, *, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self.fail:
            raise httpx.ConnectError("api unreachable")
        return SimpleNamespace(raise_for_status=lambda: None)


def _patch_http_client(monkeypatch, client):
    monkeypatch.setattr(email_service.httpx, "AsyncClient", lambda *a, **k: client)


def test_send_email_success_posts_to_resend(monkeypatch):
    client = _FakeResendClient()
    _patch_http_client(monkeypatch, client)
    monkeypatch.setattr(
        email_service, "get_settings", lambda: _settings(RESEND_API_KEY="re_123")
    )

    asyncio.run(email_service.send_verification_email("a@b.com", "tok"))

    call = client.calls[0]
    assert call["url"] == email_service.RESEND_API_URL
    assert call["headers"]["Authorization"] == "Bearer re_123"
    assert call["json"]["to"] == ["a@b.com"]
    assert call["json"]["from"] == "noreply@memoai.example.com"
    assert call["json"]["subject"] == email_service.VERIFY_SUBJECT
    assert "auth/verify?token=tok" in call["json"]["html"]
    assert "auth/verify?token=tok" in call["json"]["text"]


def test_send_email_http_error_is_swallowed(monkeypatch, caplog):
    client = _FakeResendClient(fail=True)
    _patch_http_client(monkeypatch, client)
    monkeypatch.setattr(
        email_service, "get_settings", lambda: _settings(RESEND_API_KEY="re_123")
    )

    # The auth flow must never break because an email failed to send.
    asyncio.run(email_service.send_verification_email("a@b.com", "tok"))
    assert "Failed to send email to a@b.com" in caplog.text
