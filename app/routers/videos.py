import logging
import mimetypes
import tempfile
import uuid
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import (
    course_owned_condition,
    course_readable_condition,
    get_course_or_404,
)
from app.auth import current_user
from app.config import get_settings
from app.dependencies import get_db
from app.exceptions import NotFoundError, TranscriptionError, UploadError
from app.limiter import limiter
from app.models import Course as CourseModel
from app.models import User
from app.models import Video as VideoModel
from app.schemas import Video, VideoUpdate, VideoWithTranscript
from app.services.ai import get_transcription_service
from app.services.storage import StorageService, get_storage_service
from app.services.video_service import VideoService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/videos", tags=["videos"])
settings = get_settings()

MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_BYTES
CHUNK_SIZE = 1024 * 1024
ALLOWED_MIME_PREFIXES = ("video/",)


def _looks_like_video(header: bytes) -> bool:
    """Check magic bytes of common video containers (mp4/mov/m4v, webm/mkv)."""
    if len(header) >= 8 and header[4:8] == b"ftyp":
        return True
    return header.startswith(b"\x1a\x45\xdf\xa3")


async def _get_accessible_video_or_404(
    video_id: UUID, user: User, db: AsyncSession
) -> VideoModel:
    statement = (
        select(VideoModel)
        .join(CourseModel, VideoModel.course_id == CourseModel.id)
        .where(VideoModel.id == video_id, course_readable_condition(user.id))
    )
    video = (await db.execute(statement)).scalar_one_or_none()
    if video is None:
        raise NotFoundError("Video", video_id)
    return video


async def _get_owned_video_or_404(
    video_id: UUID, user: User, db: AsyncSession
) -> VideoModel:
    statement = (
        select(VideoModel)
        .join(CourseModel, VideoModel.course_id == CourseModel.id)
        .where(VideoModel.id == video_id, course_owned_condition(user.id))
    )
    video = (await db.execute(statement)).scalar_one_or_none()
    if video is None:
        raise NotFoundError("Video", video_id)
    return video


def _try_get_url(storage: StorageService, key: str) -> str | None:
    try:
        return storage.get_url(key)
    except UploadError:
        return None


def _to_video(video: VideoModel, storage: StorageService) -> Video:
    result = Video.model_validate(video)
    result.file_url = _try_get_url(storage, video.storage_key)
    return result


def _to_video_with_transcript(
    video: VideoModel, storage: StorageService
) -> VideoWithTranscript:
    result = VideoWithTranscript.model_validate(video)
    result.file_url = _try_get_url(storage, video.storage_key)
    return result


def _build_storage_key(course_id: UUID) -> str:
    return f"course_videos/{course_id}/{uuid.uuid4().hex}.mp4"


@router.get("/", response_model=list[Video])
async def get_videos(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    title: str | None = None,
    course_id: UUID | None = None,
):
    statement = (
        select(VideoModel)
        .join(CourseModel, VideoModel.course_id == CourseModel.id)
        .where(course_readable_condition(user.id))
    )
    if title:
        statement = statement.where(VideoModel.title.contains(title))
    if course_id:
        statement = statement.where(VideoModel.course_id == course_id)
    statement = statement.offset(skip).limit(limit)
    result = await db.execute(statement)
    storage = get_storage_service()
    return [_to_video(video, storage) for video in result.scalars().all()]


@router.post("/upload", response_model=Video, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_video(
    request: Request,
    title: Annotated[str, Form()],
    course_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    description: Annotated[str | None, Form()] = None,
    generate_transcript: Annotated[bool, Form()] = True,
):
    await get_course_or_404(db, user, course_id, write=True)

    if not file.content_type or not file.content_type.startswith(ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a video",
        )

    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Video exceeds maximum size of 300 MB",
        )

    stream = tempfile.SpooledTemporaryFile(max_size=32 * CHUNK_SIZE)
    try:
        total = 0
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Video exceeds maximum size of 300 MB",
                )
            stream.write(chunk)

        if total == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="File must be a video"
            )

        stream.seek(0)
        if not _looks_like_video(stream.read(12)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="File must be a video"
            )

        stream.seek(0)
        storage = get_storage_service()
        transcription = get_transcription_service() if generate_transcript else None
        video_service = VideoService(storage, transcription)

        try:
            result = await video_service.process_upload(
                _build_storage_key(course_id),
                stream,
                file.content_type,
                generate_transcript,
            )
        except UploadError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            ) from exc

        db_video = VideoModel(
            title=title,
            description=description,
            course_id=course_id,
            storage_key=result["storage_key"],
            duration=result.get("duration"),
            transcript=result.get("transcript"),
        )
        db.add(db_video)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            try:
                await storage.delete(result["storage_key"])
            except UploadError:
                logger.exception("Failed to clean up stored video after DB error")
            raise
        await db.refresh(db_video)
        return _to_video(db_video, storage)
    finally:
        stream.close()


@router.get("/{video_id}", response_model=VideoWithTranscript)
async def get_video(
    video_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    db_video = await _get_accessible_video_or_404(video_id, user, db)
    return _to_video_with_transcript(db_video, get_storage_service())


@router.put("/{video_id}", response_model=Video)
async def update_video(
    video_id: UUID,
    video: VideoUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    db_video = await _get_owned_video_or_404(video_id, user, db)

    if video.course_id is not None and video.course_id != db_video.course_id:
        await get_course_or_404(db, user, video.course_id, write=True)

    update_data = video.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_video, key, value)

    await db.commit()
    await db.refresh(db_video)
    return _to_video(db_video, get_storage_service())


@router.get("/{video_id}/file")
async def get_video_file(
    video_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    db_video = await _get_accessible_video_or_404(video_id, user, db)
    storage = get_storage_service()

    url = _try_get_url(storage, db_video.storage_key)
    if url:
        return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    path = storage.path(db_video.storage_key)
    if path is not None and path.exists():
        media_type = mimetypes.guess_type(db_video.storage_key)[0] or "video/mp4"
        return FileResponse(path, media_type=media_type)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found"
    )


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    db_video = await _get_owned_video_or_404(video_id, user, db)
    storage_key = db_video.storage_key

    await db.delete(db_video)
    await db.commit()

    storage = get_storage_service()
    try:
        await storage.delete(storage_key)
    except UploadError as exc:
        logger.error(
            "Failed to delete stored video %s after DB removal: %s", storage_key, exc
        )
    return None


@router.post("/{video_id}/regenerate-transcript", response_model=Video)
async def regenerate_transcript(
    video_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    db_video = await _get_owned_video_or_404(video_id, user, db)

    try:
        transcription = get_transcription_service()
    except TranscriptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    storage = get_storage_service()
    video_service = VideoService(storage, transcription)
    try:
        db_video.transcript = await video_service.regenerate_transcript(
            db_video.storage_key
        )
    except UploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    await db.commit()
    await db.refresh(db_video)
    return _to_video(db_video, storage)
