import asyncio
from io import BytesIO

import pytest
from botocore.exceptions import ClientError

from app.exceptions import UploadError
from app.services.storage import (
    B2StorageService,
    LocalStorageService,
    get_storage_service,
)


class FakeSettingsLocal:
    B2_ENDPOINT_URL = ""
    B2_KEY_ID = ""
    B2_APPLICATION_KEY = ""
    B2_BUCKET_NAME = ""
    B2_REGION = ""
    STORAGE_DIR = "data/uploads"


class FakeSettingsB2:
    B2_ENDPOINT_URL = "https://s3.example.com"
    B2_KEY_ID = "key-id"
    B2_APPLICATION_KEY = "application-key"
    B2_BUCKET_NAME = "memoai-videos"
    B2_REGION = "us-west-004"
    STORAGE_DIR = "data/uploads"


class FakeB2Client:
    """Minimal S3 client fake for exercising B2StorageService logic."""

    def __init__(self):
        self.objects = {}

    def put_object(self, **kwargs):
        self.objects[kwargs["Key"]] = kwargs["Body"].read()

    def delete_object(self, **kwargs):
        self.objects.pop(kwargs["Key"], None)

    def get_object(self, **kwargs):
        key = kwargs["Key"]
        if key not in self.objects:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "missing"}},
                "GetObject",
            )
        return {"Body": _Body(self.objects[key])}

    def download_fileobj(self, **kwargs):
        kwargs["Fileobj"].write(self.objects[kwargs["Key"]])

    def generate_presigned_url(self, operation_name, Params, ExpiresIn):
        return f"https://presigned.example.test/{Params['Key']}"


class _Body:
    def __init__(self, data: bytes):
        self.data = data

    def read(self) -> bytes:
        return self.data

    def close(self) -> None:
        pass


def test_local_save_read_delete(tmp_path):
    storage = LocalStorageService(base_dir=tmp_path)
    asyncio.run(storage.save("videos/a.mp4", BytesIO(b"content"), "video/mp4"))
    assert (tmp_path / "videos" / "a.mp4").read_bytes() == b"content"
    assert asyncio.run(storage.read("videos/a.mp4")) == b"content"
    assert storage.get_url("videos/a.mp4") is None
    assert storage.path("videos/a.mp4") == tmp_path / "videos" / "a.mp4"

    asyncio.run(storage.delete("videos/a.mp4"))
    assert not (tmp_path / "videos" / "a.mp4").exists()


def test_local_read_to_file(tmp_path):
    storage = LocalStorageService(base_dir=tmp_path)
    asyncio.run(storage.save("videos/a.mp4", BytesIO(b"content"), "video/mp4"))
    dest = tmp_path / "copy.mp4"
    asyncio.run(storage.read_to_file("videos/a.mp4", dest))
    assert dest.read_bytes() == b"content"


def test_local_delete_missing_is_noop(tmp_path):
    storage = LocalStorageService(base_dir=tmp_path)
    asyncio.run(storage.delete("missing.mp4"))
    assert not (tmp_path / "missing.mp4").exists()


def test_local_read_missing_raises(tmp_path):
    storage = LocalStorageService(base_dir=tmp_path)
    with pytest.raises(UploadError):
        asyncio.run(storage.read("missing.mp4"))


def test_local_save_rejects_path_traversal(tmp_path):
    storage = LocalStorageService(base_dir=tmp_path)
    with pytest.raises(UploadError):
        asyncio.run(storage.save("../escape.mp4", BytesIO(b"x"), "video/mp4"))


def test_factory_returns_local_fallback_without_b2(monkeypatch):
    monkeypatch.setattr(
        "app.services.storage.get_settings", lambda: FakeSettingsLocal()
    )
    service = get_storage_service()
    assert isinstance(service, LocalStorageService)
    assert str(service.base_dir) == "data/uploads"


def test_factory_returns_b2_when_configured(monkeypatch):
    monkeypatch.setattr("app.services.storage.get_settings", lambda: FakeSettingsB2())
    service = get_storage_service()
    assert isinstance(service, B2StorageService)
    assert service.bucket == "memoai-videos"


def test_b2_save_read_delete_and_url():
    storage = B2StorageService(
        endpoint_url="https://s3.example.com",
        key_id="key-id",
        application_key="key",
        bucket="memoai-videos",
        region="us-west-004",
    )
    storage.client = FakeB2Client()

    asyncio.run(storage.save("videos/a.mp4", BytesIO(b"content"), "video/mp4"))
    assert asyncio.run(storage.read("videos/a.mp4")) == b"content"
    assert (
        storage.get_url("videos/a.mp4") == "https://presigned.example.test/videos/a.mp4"
    )

    asyncio.run(storage.delete("videos/a.mp4"))
    with pytest.raises(UploadError):
        asyncio.run(storage.read("videos/a.mp4"))


def _make_client_error(operation: str) -> ClientError:
    return ClientError({"Error": {"Code": "Err", "Message": "boom"}}, operation)


class _FailingB2Client:
    def put_object(self, **kwargs):
        raise _make_client_error("PutObject")

    def delete_object(self, **kwargs):
        raise _make_client_error("DeleteObject")

    def get_object(self, **kwargs):
        raise _make_client_error("GetObject")

    def download_fileobj(self, **kwargs):
        raise _make_client_error("GetObject")

    def generate_presigned_url(self, operation_name, Params, ExpiresIn):
        raise _make_client_error("GetObject")


def _make_b2_service() -> B2StorageService:
    storage = B2StorageService(
        endpoint_url="https://s3.example.com",
        key_id="key-id",
        application_key="key",
        bucket="memoai-videos",
        region="us-west-004",
    )
    storage.client = _FailingB2Client()
    return storage


def test_b2_save_error_raises():
    with pytest.raises(UploadError):
        asyncio.run(_make_b2_service().save("k.mp4", BytesIO(b"x"), "video/mp4"))


def test_b2_delete_error_raises():
    with pytest.raises(UploadError):
        asyncio.run(_make_b2_service().delete("k.mp4"))


def test_b2_read_error_raises():
    with pytest.raises(UploadError):
        asyncio.run(_make_b2_service().read("k.mp4"))


def test_b2_read_to_file_success(tmp_path):
    storage = B2StorageService(
        endpoint_url="https://s3.example.com",
        key_id="key-id",
        application_key="key",
        bucket="memoai-videos",
        region="us-west-004",
    )
    storage.client = FakeB2Client()
    asyncio.run(storage.save("videos/a.mp4", BytesIO(b"content"), "video/mp4"))

    dest = tmp_path / "copy.mp4"
    asyncio.run(storage.read_to_file("videos/a.mp4", dest))
    assert dest.read_bytes() == b"content"


def test_b2_read_to_file_error_raises(tmp_path):
    with pytest.raises(UploadError):
        asyncio.run(_make_b2_service().read_to_file("k.mp4", tmp_path / "x.mp4"))


def test_b2_get_url_error_raises():
    with pytest.raises(UploadError):
        _make_b2_service().get_url("k.mp4")


def test_local_save_oserror_raises(tmp_path, monkeypatch):
    storage = LocalStorageService(base_dir=tmp_path)

    def _boom_write(path, data):
        raise OSError("disk full")

    monkeypatch.setattr(LocalStorageService, "_write_stream", staticmethod(_boom_write))
    with pytest.raises(UploadError):
        asyncio.run(storage.save("videos/a.mp4", BytesIO(b"x"), "video/mp4"))


def test_local_delete_oserror_raises(tmp_path, monkeypatch):
    storage = LocalStorageService(base_dir=tmp_path)
    asyncio.run(storage.save("a.mp4", BytesIO(b"x"), "video/mp4"))

    def _boom_unlink(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr("pathlib.Path.unlink", _boom_unlink)
    with pytest.raises(UploadError):
        asyncio.run(storage.delete("a.mp4"))
