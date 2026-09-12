import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Any, BinaryIO

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
        file_obj: BinaryIO,
        content_type: str,
        generate_transcript: bool,
    ) -> dict[str, Any]:
        file_obj.seek(0)
        duration = await asyncio.to_thread(self._probe_duration, file_obj)

        file_obj.seek(0)
        await self.storage.save(key, file_obj, content_type)

        transcript = None
        if generate_transcript:
            file_obj.seek(0)
            transcript = await self._generate_transcript(file_obj)

        return {
            "storage_key": key,
            "duration": duration,
            "transcript": transcript,
        }

    async def regenerate_transcript(self, key: str) -> str:
        local_path = self.storage.path(key)
        if local_path is not None and local_path.exists():
            with open(local_path, "rb") as f:
                return await self._generate_transcript(f)

        fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        try:
            await self.storage.read_to_file(key, tmp_path)
            with open(tmp_path, "rb") as f:
                return await self._generate_transcript(f)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def _generate_transcript(self, file_obj: BinaryIO) -> str:
        if self.transcription is None:
            return "Transcription not available"
        try:
            return await asyncio.to_thread(self.transcription.transcribe_file, file_obj)
        except TranscriptionError:
            logger.warning("Transcription failed for uploaded video")
            return "Transcription not available"

    def _probe_duration(self, file_obj: BinaryIO) -> int | None:
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
                shutil.copyfileobj(file_obj, temp_file)
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
