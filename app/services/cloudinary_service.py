import logging
import os
import tempfile
from typing import Any

import cloudinary
import cloudinary.uploader

from app.config import get_settings
from app.exceptions import UploadError

logger = logging.getLogger(__name__)


class CloudinaryService:
    def __init__(self):
        settings = get_settings()
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
        )

    def upload_bytes(
        self, file_bytes: bytes, folder: str = "course_videos", suffix: str = ".mp4"
    ) -> dict[str, Any]:
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name

            result = cloudinary.uploader.upload(
                temp_path,
                resource_type="video",
                folder=folder,
                overwrite=True,
                quality="auto",
                fetch_format="auto",
            )

            return {
                "public_id": result["public_id"],
                "url": result["url"],
                "secure_url": result["secure_url"],
                "format": result.get("format"),
                "resource_type": result["resource_type"],
                "duration": result.get("duration"),
            }
        except Exception as exc:
            logger.error("Cloudinary upload failed: %s", exc)
            raise UploadError("Failed to upload video to cloud storage") from exc
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def delete(self, public_id: str) -> dict[str, Any]:
        try:
            return cloudinary.uploader.destroy(public_id, resource_type="video")
        except Exception as exc:
            logger.error("Cloudinary delete failed for %s: %s", public_id, exc)
            raise UploadError("Failed to delete video from cloud storage") from exc
