import asyncio
import logging
import shutil
from pathlib import Path
from typing import BinaryIO

from app.exceptions import UploadError
from app.services.storage.base import StorageService

logger = logging.getLogger(__name__)


class LocalStorageService(StorageService):
    """Stores files on the local filesystem (dev/test fallback storage)."""

    def __init__(self, base_dir: str | Path = "data/uploads"):
        self.base_dir = Path(base_dir)

    def _resolve(self, key: str) -> Path:
        path = (self.base_dir / key).resolve()
        if not path.is_relative_to(self.base_dir.resolve()):
            raise UploadError("Invalid storage key")
        return path

    async def save(self, key: str, data: BinaryIO, content_type: str) -> None:
        path = self._resolve(key)
        try:
            await asyncio.to_thread(self._write_stream, path, data)
        except OSError as exc:
            logger.error("Local storage save failed for %s: %s", key, exc)
            raise UploadError("Failed to upload video to storage") from exc

    @staticmethod
    def _write_stream(path: Path, data: BinaryIO) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as dst:
            while chunk := data.read(1024 * 1024):
                dst.write(chunk)

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.error("Local storage delete failed for %s: %s", key, exc)
            raise UploadError("Failed to delete video from storage") from exc

    async def read(self, key: str) -> bytes:
        path = self._resolve(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except OSError as exc:
            logger.error("Local storage read failed for %s: %s", key, exc)
            raise UploadError("Failed to read video from storage") from exc

    async def read_to_file(self, key: str, dest_path: str | Path) -> None:
        path = self._resolve(key)
        try:
            await asyncio.to_thread(shutil.copyfile, path, dest_path)
        except OSError as exc:
            logger.error("Local storage read failed for %s: %s", key, exc)
            raise UploadError("Failed to read video from storage") from exc

    def path(self, key: str) -> Path:
        return self.base_dir / key
