from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO


class StorageService(ABC):
    """Interface for storing and retrieving user-uploaded content."""

    @abstractmethod
    async def save(self, key: str, data: BinaryIO, content_type: str) -> None:
        """Store the stream content (read from its current position)."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove the content stored under the given key (no-op if missing)."""

    @abstractmethod
    async def read(self, key: str) -> bytes:
        """Return the raw content stored under the given key."""

    @abstractmethod
    async def read_to_file(self, key: str, dest_path: str | Path) -> None:
        """Stream the content stored under the given key to a local file."""

    def get_url(self, key: str) -> str | None:
        """Return a URL the client can fetch content from, if available."""
        return None

    def path(self, key: str) -> Path | None:
        """Return a local filesystem path for the content, if available."""
        return None
