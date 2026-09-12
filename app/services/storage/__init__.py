from urllib.parse import urlparse

from app.config import get_settings
from app.services.storage.backblaze import B2StorageService
from app.services.storage.base import StorageService
from app.services.storage.local import LocalStorageService

__all__ = [
    "StorageService",
    "B2StorageService",
    "LocalStorageService",
    "get_storage_service",
]

_DEFAULT_REGION = "us-west-004"


def _derive_region(endpoint_url: str) -> str | None:
    host = urlparse(endpoint_url).hostname or ""
    if host.startswith("s3.") and host.endswith(".backblazeb2.com"):
        return host[len("s3.") : -len(".backblazeb2.com")]
    return None


def get_storage_service() -> StorageService:
    """Return Backblaze B2 storage when configured, otherwise local fallback."""
    settings = get_settings()
    if (
        settings.B2_ENDPOINT_URL
        and settings.B2_KEY_ID
        and settings.B2_APPLICATION_KEY
        and settings.B2_BUCKET_NAME
    ):
        region = (
            settings.B2_REGION
            or _derive_region(settings.B2_ENDPOINT_URL)
            or _DEFAULT_REGION
        )
        return B2StorageService(
            endpoint_url=settings.B2_ENDPOINT_URL,
            key_id=settings.B2_KEY_ID,
            application_key=settings.B2_APPLICATION_KEY,
            bucket=settings.B2_BUCKET_NAME,
            region=region,
        )
    return LocalStorageService(base_dir=settings.STORAGE_DIR)
