from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.exceptions import NotFoundError, UploadError
from app.models import Course as CourseModel
from app.models import Video as VideoModel
from app.schemas import Video, VideoUpdate, VideoWithTranscript
from app.services.ai import get_transcription_service
from app.services.cloudinary_service import CloudinaryService
from app.services.video_service import VideoService

router = APIRouter(prefix="/videos", tags=["videos"])

MAX_UPLOAD_BYTES = 300 * 1024 * 1024
ALLOWED_MIME_PREFIXES = ("video/",)


async def _get_video_or_404(video_id: int, db: AsyncSession) -> VideoModel:
    result = await db.execute(select(VideoModel).where(VideoModel.id == video_id))
    video = result.scalar_one_or_none()
    if video is None:
        raise NotFoundError("Video", video_id)
    return video


async def _get_course_or_404(course_id: int, db: AsyncSession) -> CourseModel:
    result = await db.execute(select(CourseModel).where(CourseModel.id == course_id))
    course = result.scalar_one_or_none()
    if course is None:
        raise NotFoundError("Course", course_id)
    return course


@router.get("/", response_model=list[Video])
async def get_videos(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
    title: str | None = None,
    course_id: int | None = None,
):
    statement = select(VideoModel)
    if title:
        statement = statement.where(VideoModel.title.contains(title))
    if course_id:
        statement = statement.where(VideoModel.course_id == course_id)
    result = await db.execute(statement.offset(skip).limit(limit))
    return result.scalars().all()


@router.post("/upload", response_model=Video, status_code=status.HTTP_201_CREATED)
async def upload_video(
    title: Annotated[str, Form()],
    course_id: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
    db: Annotated[AsyncSession, Depends(get_db)],
    description: Annotated[str | None, Form()] = None,
    generate_transcript: Annotated[bool, Form()] = True,
):
    await _get_course_or_404(course_id, db)

    if not file.content_type or not file.content_type.startswith(ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a video",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Video exceeds maximum size of 300 MB",
        )

    cloudinary_service = CloudinaryService()
    transcription_service = get_transcription_service()
    video_service = VideoService(cloudinary_service, transcription_service)

    try:
        result = video_service.process_upload(file_bytes, generate_transcript)
    except UploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    db_video = VideoModel(
        title=title,
        description=description,
        course_id=course_id,
        cloudinary_public_id=result["cloudinary_public_id"],
        cloudinary_url=result["cloudinary_url"],
        duration=result.get("duration"),
        transcript=result.get("transcript"),
    )
    db.add(db_video)
    await db.commit()
    await db.refresh(db_video)
    return db_video


@router.get("/{video_id}", response_model=VideoWithTranscript)
async def get_video(video_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    return await _get_video_or_404(video_id, db)


@router.put("/{video_id}", response_model=Video)
async def update_video(
    video_id: int, video: VideoUpdate, db: Annotated[AsyncSession, Depends(get_db)]
):
    db_video = await _get_video_or_404(video_id, db)

    if video.course_id is not None and video.course_id != db_video.course_id:
        await _get_course_or_404(video.course_id, db)

    update_data = video.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_video, key, value)

    await db.commit()
    await db.refresh(db_video)
    return db_video


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(video_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    db_video = await _get_video_or_404(video_id, db)

    cloudinary_service = CloudinaryService()
    try:
        cloudinary_service.delete(db_video.cloudinary_public_id)
    except UploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    await db.delete(db_video)
    await db.commit()
    return None


@router.post("/{video_id}/regenerate-transcript", response_model=Video)
async def regenerate_transcript(
    video_id: int, db: Annotated[AsyncSession, Depends(get_db)]
):
    db_video = await _get_video_or_404(video_id, db)

    transcription_service = get_transcription_service()
    db_video.transcript = transcription_service.transcribe_url(db_video.cloudinary_url)

    await db.commit()
    await db.refresh(db_video)
    return db_video
