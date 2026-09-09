import asyncio
import logging
from pathlib import Path

from app.exceptions import UploadError
from app.services.storage.base import StorageService

logger = logging.getLogger(__name__)


class LocalStorageService(StorageService):
    """Stores files on the local filesystem.

    Used in development, tests and CI: it requires no external credentials
    and is the default fallback when Backblaze B2 is not configured.
    """

    def __init__(self, base_dir: str | Path = "data/uploads"):
        self.base_dir = Path(base_dir)

    def _resolve(self, key: str) -> Path:
        path = (self.base_dir / key).resolve()
        if not path.is_relative_to(self.base_dir.resolve()):
            raise UploadError("Invalid storage key")
        return path

    async def save(self, key: str, data: bytes, content_type: str) -> None:
        path = self._resolve(key)
        try:
            await asyncio.to_thread(self._write, path, data)
        except OSError as exc:
            logger.error("Local storage save failed for %s: %s", key, exc)
            raise UploadError("Failed to upload video to storage") from exc

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

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

    def path(self, key: str) -> Path:
        return self.base_dir / key
