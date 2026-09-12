import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
VERIFY_SUBJECT = "Verify your MemoAI account"
RESET_SUBJECT = "Reset your MemoAI password"


def _build_url(path: str, token: str) -> str:
    settings = get_settings()
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return f"{base}{path}?token={token}"


async def _send_email(to_email: str, subject: str, html: str, text: str) -> None:
    settings = get_settings()
    if not settings.RESEND_API_KEY:
        if not settings.is_production:
            logger.info("[dev] Email to %s: %s\n%s", to_email, subject, text)
        else:
            logger.error("Email not sent: RESEND_API_KEY is missing")
        return
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                RESEND_API_URL,
                json={
                    "from": settings.EMAIL_FROM,
                    "to": [to_email],
                    "subject": subject,
                    "html": html,
                    "text": text,
                },
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        # Never break the auth flow because an email failed to send; the
        # user can request a new token.
        logger.error("Failed to send email to %s: %s", to_email, exc)


async def send_verification_email(email: str, token: str) -> None:
    url = _build_url("/auth/verify", token)
    await _send_email(
        email,
        VERIFY_SUBJECT,
        html=f'<p>Open this link to verify your email: <a href="{url}">{url}</a></p>',
        text=f"Open this link to verify your email: {url}",
    )


async def send_password_reset_email(email: str, token: str) -> None:
    url = _build_url("/auth/reset-password", token)
    await _send_email(
        email,
        RESET_SUBJECT,
        html=f'<p>Open this link to reset your password: <a href="{url}">{url}</a></p>',
        text=f"Open this link to reset your password: {url}",
    )
