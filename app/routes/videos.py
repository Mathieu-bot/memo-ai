from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional

from app.schemas.video import Video, VideoCreate, VideoUpdate, VideoUpload, VideoWithTranscript
from app.services.db import get_db
from app.services.ai_service import AIService
from app.services.cloudinary_service import CloudinaryService
from app.models.video import Video as VideoModel
from app.models.course import Course as CourseModel

router = APIRouter(prefix="/videos", tags=["videos"])

@router.get("/", response_model=List[Video])
def get_videos(
        skip: int = 0,
        limit: int = 100,
        title: Optional[str] = None,
        course_id: Optional[int] = None,
        db: Session = Depends(get_db)
):
    ## Get all videos with options of filtering.
    query = db.query(VideoModel)
    if title:
        query = query.filter(VideoModel.title.contains(title))
    if course_id:
        query = query.filter(VideoModel.course_id == course_id)
    videos = query.offset(skip).limit(limit).all()
    return videos

@router.post("/upload", response_model=Video, status_code=status.HTTP_201_CREATED)
def upload_video(video_data: VideoUpload, generate_transcript: bool = True, db: Session = Depends(get_db)):
    course = db.query(CourseModel).filter(CourseModel.id == video_data.course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    try:
        upload_result = CloudinaryService.upload_video(video_data.file)
        db_video = VideoModel(
            title=video_data.title,
            description=video_data.description,
            course_id=video_data.course_id,
            cloudinary_public_id=upload_result["public_id"],
            cloudinary_url=upload_result["secure_url"],
            duration=upload_result.get("duration")
        )

        db.add(db_video)
        db.flush()

        if generate_transcript:
            transcript = AIService.generate_transcript(db_video.cloudinary_url)
            db_video.transcript = transcript

        db.commit()
        db.refresh(db_video)
        return db_video

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))  # binascii.Error (invalid Base64)
    except Exception as e:
        db.rollback()
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