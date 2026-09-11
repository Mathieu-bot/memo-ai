from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.exceptions import (
    AIServiceError,
    NotFoundError,
    ai_service_handler,
    global_exception_handler,
    not_found_handler,
)
from app.logging_config import configure_logging
from app.routers import ai, auth, courses, notes, quizzes, videos
from app.utils.net import prefer_ipv4

settings = get_settings()


def create_app() -> FastAPI:
    configure_logging()
    if settings.NET_IPV4_ONLY:
        prefer_ipv4()
    app = FastAPI(
        title="MemoAI API",
        description="Memorization assistant API for students",
        version="2.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
