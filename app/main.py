from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.exceptions import (
    AIServiceError,
    NotFoundError,
    ai_service_handler,
    global_exception_handler,
    not_found_handler,
)
from app.limiter import limiter
from app.logging_config import configure_logging
from app.routers import ai, auth, courses, notes, quizzes, videos
from app.utils.net import prefer_ipv4
from app.utils.ratelimit import FixedWindowRateLimiter

settings = get_settings()


def _auth_limiter() -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(settings.RATE_LIMIT_AUTH)


def _validate_production_settings() -> None:
    if not settings.is_production:
        return
    if not settings.PUBLIC_BASE_URL:
        raise RuntimeError("PUBLIC_BASE_URL must be set in production")
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY must be set in production")
    if not settings.RATE_LIMITING_ENABLED:
        raise RuntimeError("RATE_LIMITING_ENABLED cannot be false in production")
    if "*" in settings.CORS_ORIGINS:
        raise RuntimeError("CORS_ORIGINS must not contain '*' in production")


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests"})


def create_app() -> FastAPI:
    _validate_production_settings()
    configure_logging()
    if settings.NET_IPV4_ONLY:
        prefer_ipv4()
    app = FastAPI(
        title="MemoAI API",
        description="Memorization assistant API for students",
        version="2.0.0",
    )

    allow_all_origins = "*" in settings.CORS_ORIGINS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=not allow_all_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    limiter.enabled = settings.RATE_LIMITING_ENABLED
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    auth_rate_limiter = _auth_limiter()

    @app.middleware("http")
    async def limit_auth_requests(request: Request, call_next):
        if settings.RATE_LIMITING_ENABLED and request.url.path.startswith("/auth/"):
            ip = request.client.host if request.client else "unknown"
            if not auth_rate_limiter.allow(ip):
                return JSONResponse(
                    status_code=429, content={"detail": "Too many requests"}
                )
        return await call_next(request)

    app.include_router(auth.router)
    app.include_router(courses.router)
    app.include_router(quizzes.router)
    app.include_router(notes.router)
    app.include_router(videos.router)
    app.include_router(ai.router)

    app.add_exception_handler(NotFoundError, not_found_handler)
    app.add_exception_handler(AIServiceError, ai_service_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    return app


app = create_app()
