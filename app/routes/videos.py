from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
import re

from app.schemas.video import Video, VideoCreate, VideoUpdate, VideoWithTranscript
from app.services.db import get_db
from app.services.ai_service import AIService
from app.services.cloudinary_service import CloudinaryService
from app.models.video import Video as VideoModel
from app.models.course import Course as CourseModel

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/videos", tags=["videos"])

@router.get("/", response_model=List[Video])
def get_videos(
        skip: int = 0,
        limit: int = 100,
        title: Optional[str] = None,
        course_id: Optional[int] = None,
        db: Session = Depends(get_db)
):
    query = db.query(VideoModel)
    if title:
        query = query.filter(VideoModel.title.contains(title))
    if course_id:
        query = query.filter(VideoModel.course_id == course_id)
    videos = query.offset(skip).limit(limit).all()
    return videos

@router.post("/upload", response_model=Video, status_code=status.HTTP_201_CREATED)
async def upload_video(
        file: UploadFile = File(...),
        title: str = Form(...),
        description: Optional[str] = Form(None),
        course_id: int = Form(...),
        generate_transcript: bool = True,
        db: Session = Depends(get_db)
):
    if not file.content_type.startswith("video/"):
        logger.error(f"Invalid file type: {file.content_type}")
        raise HTTPException(status_code=400, detail="Invalid video file format. Only video files (e.g., mp4, webm) are allowed.")

    course = db.query(CourseModel).filter(CourseModel.id == course_id).first()
    if course is None:
        logger.error(f"Course not found: course_id={course_id}")
        raise HTTPException(status_code=404, detail="Course not found")

    try:
        file_data = await file.read()
        upload_result: Dict[str, Any] = CloudinaryService.upload_video(file_data)

        required_keys = ["public_id", "secure_url"]
        missing_keys = [key for key in required_keys if key not in upload_result]
        if missing_keys:
            logger.error(f"Missing keys in upload_result: {missing_keys}")
            raise HTTPException(
                status_code=500,
                detail=f"Cloudinary upload failed: missing keys {missing_keys}"
            )

        secure_url = upload_result["secure_url"]
        public_id = upload_result["public_id"]
        if not re.match(r'^https?://', secure_url):
            logger.error(f"Invalid Cloudinary URL: {secure_url}")
            raise HTTPException(status_code=400, detail="Invalid Cloudinary URL")
        if not re.match(r'^[a-zA-Z0-9_-]+$', public_id):
            logger.error(f"Invalid Cloudinary public ID: {public_id}")
            raise HTTPException(status_code=400, detail="Invalid Cloudinary public ID")

        db_video = VideoModel(
            title=title,
            description=description,
            course_id=course_id,
            cloudinary_public_id=public_id,
            cloudinary_url=secure_url,
            duration=upload_result.get("duration")
        )

        db.add(db_video)
        db.flush()

        if generate_transcript:
            transcript = AIService.generate_transcript(db_video.cloudinary_url)
            db_video.transcript = transcript

        db.commit()
        db.refresh(db_video)
        logger.info(f"Video uploaded successfully: id={db_video.id}, title={title}")
        return db_video

    except ValueError as e:
        db.rollback()
        logger.error(f"ValueError during video upload: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during video upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while uploading the video: {str(e)}"
        )

@router.get("/{video_id}", response_model=VideoWithTranscript)
def get_video(video_id: int, db: Session = Depends(get_db)):
    video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@router.put("/{video_id}", response_model=Video)
def update_video(video_id: int, video: VideoUpdate, db: Session = Depends(get_db)):
    db_video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if db_video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    if video.course_id is not None and video.course_id != db_video.course_id:
        course = db.query(CourseModel).filter(CourseModel.id == video.course_id).first()
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")

    update_data = video.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_video, key, value)

    db.commit()
    db.refresh(db_video)
    return db_video

@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(video_id: int, db: Session = Depends(get_db)):
    db_video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if db_video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        CloudinaryService.delete_video(db_video.cloudinary_public_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while deleting video in Cloudinary: {str(e)}"
        )

    db.delete(db_video)
    db.commit()
    return None

@router.post("/{video_id}/regenerate-transcript", response_model=Video)
def regenerate_transcript(video_id: int, db: Session = Depends(get_db)):
    db_video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if db_video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    db_video.transcript = AIService.generate_transcript(db_video.cloudinary_url)
    db.commit()
    db.refresh(db_video)
    return db_video