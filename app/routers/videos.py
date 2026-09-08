from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

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


def _get_video_or_404(video_id: int, db: Session) -> VideoModel:
    video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if video is None:
        raise NotFoundError("Video", video_id)
    return video


def _get_course_or_404(course_id: int, db: Session) -> CourseModel:
    course = db.query(CourseModel).filter(CourseModel.id == course_id).first()
    if course is None:
        raise NotFoundError("Course", course_id)
    return course


@router.get("/", response_model=list[Video])
def get_videos(
    db: Annotated[Session, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
    title: str | None = None,
    course_id: int | None = None,
):
    query = db.query(VideoModel)
    if title:
        query = query.filter(VideoModel.title.contains(title))
    if course_id:
        query = query.filter(VideoModel.course_id == course_id)
    return query.offset(skip).limit(limit).all()


@router.post("/upload", response_model=Video, status_code=status.HTTP_201_CREATED)
async def upload_video(
    title: Annotated[str, Form()],
    course_id: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    description: Annotated[str | None, Form()] = None,
    generate_transcript: Annotated[bool, Form()] = True,
):
    _get_course_or_404(course_id, db)

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
    db.commit()
    db.refresh(db_video)
    return db_video


@router.get("/{video_id}", response_model=VideoWithTranscript)
def get_video(video_id: int, db: Annotated[Session, Depends(get_db)]):
    return _get_video_or_404(video_id, db)


@router.put("/{video_id}", response_model=Video)
def update_video(
    video_id: int, video: VideoUpdate, db: Annotated[Session, Depends(get_db)]
):
    db_video = _get_video_or_404(video_id, db)

    if video.course_id is not None and video.course_id != db_video.course_id:
        _get_course_or_404(video.course_id, db)

    update_data = video.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_video, key, value)

    db.commit()
    db.refresh(db_video)
    return db_video


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(video_id: int, db: Annotated[Session, Depends(get_db)]):
    db_video = _get_video_or_404(video_id, db)

    cloudinary_service = CloudinaryService()
    try:
        cloudinary_service.delete(db_video.cloudinary_public_id)
    except UploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    db.delete(db_video)
    db.commit()
    return None


@router.post("/{video_id}/regenerate-transcript", response_model=Video)
def regenerate_transcript(video_id: int, db: Annotated[Session, Depends(get_db)]):
    db_video = _get_video_or_404(video_id, db)

    transcription_service = get_transcription_service()
    db_video.transcript = transcription_service.transcribe_url(db_video.cloudinary_url)

    db.commit()
    db.refresh(db_video)
    return db_video
