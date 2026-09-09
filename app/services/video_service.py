import asyncio
import logging
import os
import subprocess
import tempfile
from typing import Any

from app.exceptions import TranscriptionError
from app.services.ai.transcription_service import TranscriptionService
from app.services.storage import StorageService

logger = logging.getLogger(__name__)


class VideoService:
    def __init__(
        self,
        storage: StorageService,
        transcription: TranscriptionService | None = None,
    ):
        self.storage = storage
        self.transcription = transcription

    async def process_upload(
        self,
        key: str,
        file_bytes: bytes,
        content_type: str,
        generate_transcript: bool,
    ) -> dict[str, Any]:
        await self.storage.save(key, file_bytes, content_type)
        duration = await asyncio.to_thread(self._probe_duration, file_bytes)
        result: dict[str, Any] = {
            "storage_key": key,
            "duration": duration,
            "transcript": None,
        }

        if generate_transcript:
            result["transcript"] = await self._generate_transcript(file_bytes)

        return result

    async def regenerate_transcript(self, key: str) -> str:
        data = await self.storage.read(key)
        return await self._generate_transcript(data)

    async def _generate_transcript(self, file_bytes: bytes) -> str:
        if self.transcription is None:
            return "Transcription not available"
        try:
            return await asyncio.to_thread(
                self.transcription.transcribe_bytes, file_bytes
            )
        except TranscriptionError:
            logger.warning("Transcription failed for uploaded video")
            return "Transcription not available"

    def _probe_duration(self, file_bytes: bytes) -> int | None:
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name

            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                temp_path,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=30
            )
            return int(float(result.stdout.strip()))
        except Exception:
            logger.debug("Could not probe video duration")
            return None
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
