import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class NotFoundError(Exception):
    def __init__(self, resource: str, resource_id: int | None = None):
        if resource_id is not None:
            self.message = f"{resource} with id {resource_id} not found"
        else:
            self.message = f"{resource} not found"
        super().__init__(self.message)


class AIServiceError(Exception):
    def __init__(self, message: str = "AI service unavailable"):
        self.message = message
        super().__init__(self.message)


class TranscriptionError(Exception):
    def __init__(self, message: str = "Transcription failed"):
        self.message = message
        super().__init__(self.message)


class UploadError(Exception):
    def __init__(self, message: str = "Upload failed"):
        self.message = message
        super().__init__(self.message)


async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": exc.message},
    )


async def ai_service_handler(request: Request, exc: AIServiceError):
    return JSONResponse(
        status_code=503,
        content={"detail": exc.message},
    )


async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
