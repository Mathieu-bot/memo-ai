import logging
from typing import Any

from app.exceptions import TranscriptionError
from app.services.ai.transcription_service import TranscriptionService
from app.services.cloudinary_service import CloudinaryService

logger = logging.getLogger(__name__)


class VideoService:
    def __init__(
        self,
        cloudinary_service: CloudinaryService,
        transcription_service: TranscriptionService,
    ):
        self.cloudinary = cloudinary_service
        self.transcription = transcription_service

    def process_upload(
        self, file_bytes: bytes, generate_transcript: bool
    ) -> dict[str, Any]:
        upload_data = self.cloudinary.upload_bytes(file_bytes)
        result: dict[str, Any] = {
            "cloudinary_public_id": upload_data["public_id"],
            "cloudinary_url": upload_data["secure_url"],
            "duration": upload_data.get("duration"),
            "transcript": None,
        }

        if generate_transcript:
            result["transcript"] = self._generate_transcript(upload_data["secure_url"])

        return result

    def _generate_transcript(self, video_url: str) -> str:
        try:
            return self.transcription.transcribe_url(video_url)
        except TranscriptionError:
            logger.warning("Transcription failed for video %s", video_url)
            return "Transcription not available"
