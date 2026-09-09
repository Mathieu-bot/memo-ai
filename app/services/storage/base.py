from abc import ABC, abstractmethod
from pathlib import Path


class StorageService(ABC):
    """Interface for storing and retrieving user-uploaded content."""

    @abstractmethod
    async def save(self, key: str, data: bytes, content_type: str) -> None:
        """Store content under the given key."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove the content stored under the given key (no-op if missing)."""

    @abstractmethod
    async def read(self, key: str) -> bytes:
        """Return the raw content stored under the given key."""

    def get_url(self, key: str) -> str | None:
        """Return a URL the client can fetch content from, if available."""
        return None

    def path(self, key: str) -> Path | None:
        """Return a local filesystem path for the content, if available."""
        return None
