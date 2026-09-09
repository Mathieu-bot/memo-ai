import logging
import os
import shutil
import subprocess
import tempfile

import httpx
from groq import Groq

from app.config import get_settings
from app.exceptions import TranscriptionError

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_MB = 25
CHUNK_TARGET_SIZE_MB = 24


class TranscriptionService:
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)

    def transcribe_url(self, url: str) -> str:
        temp_path = self._download(url)
        try:
            return self.transcribe_path(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def transcribe_bytes(self, data: bytes, suffix: str = ".mp4") -> str:
        """Transcribe content already in memory (no download round-trip)."""
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(data)
                temp_path = temp_file.name
            return self.transcribe_path(temp_path)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def _download(self, url: str) -> str:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        tmp_path = tmp.name
        tmp.close()
        try:
            with httpx.stream(
                "GET", url, follow_redirects=True, timeout=300
            ) as response:
                response.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)
            return tmp_path
        except Exception as exc:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            logger.error("Failed to download %s: %s", url, exc)
            raise TranscriptionError() from exc

    def transcribe_path(self, file_path: str) -> str:
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            logger.info(
                "File %s is %.1f MB, splitting into chunks", file_path, file_size_mb
            )
            return self._transcribe_in_chunks(file_path)
        return self._transcribe_file(file_path)

    def _transcribe_file(self, file_path: str) -> str:
        try:
            with open(file_path, "rb") as audio_file:
                result = self.client.audio.transcriptions.create(
                    file=(os.path.basename(file_path), audio_file.read()),
                    model="whisper-large-v3-turbo",
                )
            return result.text
        except Exception as exc:
            logger.error("Groq transcription failed: %s", exc)
            raise TranscriptionError() from exc

    def _transcribe_in_chunks(self, file_path: str) -> str:
        chunks = self._split_audio(file_path)
        transcripts = []
        try:
            for chunk_path in chunks:
                transcripts.append(self._transcribe_file(chunk_path))
                os.unlink(chunk_path)
        finally:
            for chunk_path in chunks:
                if os.path.exists(chunk_path):
                    os.unlink(chunk_path)
        return "\n".join(t for t in transcripts if t)

    def _split_audio(self, file_path: str) -> list[str]:
        tmp_dir = tempfile.mkdtemp(prefix="memoai_audio_")
        segments = []
        try:
            duration = self._get_duration(file_path)
            if not duration:
                raise TranscriptionError("Could not determine audio duration")
            segment_duration = self._estimate_segment_duration(file_path, duration)
            start = 0.0
            index = 0
            while start < duration:
                segment_path = os.path.join(tmp_dir, f"segment_{index}.mp3")
                self._extract_segment(file_path, segment_path, start, segment_duration)
                segments.append(segment_path)
                start += segment_duration
                index += 1
            return segments
        except Exception:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise TranscriptionError("Failed to split audio into chunks") from None

    def _get_duration(self, file_path: str) -> float | None:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=30
            )
            return float(result.stdout.strip())
        except (subprocess.SubprocessError, ValueError):
            return None

    def _estimate_segment_duration(
        self, file_path: str, total_duration: float
    ) -> float:
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        avg_mb_per_sec = file_size_mb / total_duration if total_duration else 0
        if avg_mb_per_sec <= 0:
            return 300
        segment_duration = min(CHUNK_TARGET_SIZE_MB / avg_mb_per_sec, total_duration)
        return max(segment_duration, 10)

    def _extract_segment(
        self, source: str, target: str, start: float, duration: float
    ) -> None:
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            f"{start:.2f}",
            "-t",
            f"{duration:.2f}",
            "-i",
            source,
            "-q:a",
            "0",
            "-map",
            "a",
            "-y",
            target,
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=300)
        except subprocess.SubprocessError as exc:
            logger.error("ffmpeg segment extraction failed: %s", exc)
            raise TranscriptionError() from exc


def get_transcription_service() -> TranscriptionService:
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        raise TranscriptionError("GROQ_API_KEY is not configured")
    return TranscriptionService(api_key=settings.GROQ_API_KEY)
