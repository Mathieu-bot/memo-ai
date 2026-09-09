import asyncio
import subprocess

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse, RedirectResponse

import app.routers.videos as videos_router
from app.exceptions import NotFoundError, TranscriptionError, UploadError
from app.models import Video as VideoModel
from app.routers.courses import create_course
from app.routers.videos import (
    delete_video,
    get_video,
    get_video_file,
    get_videos,
    regenerate_transcript,
    update_video,
)
from app.schemas import CourseCreate, VideoUpdate
from app.services.storage import LocalStorageService
from app.services.video_service import VideoService
from tests.conftest import TestingSessionLocal


def _create_course(auth_client) -> dict:
    return auth_client.post("/courses/", json={"title": "Math"}).json()


def _upload(
    auth_client,
    course,
    tmp_path,
    monkeypatch,
    file_bytes=b"fake-video-bytes",
    storage=None,
):
    if storage is None:
        storage = LocalStorageService(base_dir=tmp_path)
    monkeypatch.setattr(videos_router, "get_storage_service", lambda: storage)
    response = auth_client.post(
        "/videos/upload",
        data={
            "title": "Intro",
            "course_id": str(course["id"]),
            "generate_transcript": "false",
        },
        files={"file": ("intro.mp4", file_bytes, "video/mp4")},
    )
    assert response.status_code == 201, response.text
    return response.json(), storage


class FakeTranscription:
    def __init__(self, text="Fresh transcript"):
        self.text = text

    def transcribe_bytes(self, data, suffix=".mp4"):
        return self.text


class FailingTranscription:
    def transcribe_bytes(self, data, suffix=".mp4"):
        raise TranscriptionError()


def test_video_upload_rejects_non_video(auth_client):
    course = _create_course(auth_client)
    response = auth_client.post(
        "/videos/upload",
        data={"title": "Vid", "course_id": str(course["id"])},
        files={"file": ("notes.txt", b"not a video", "text/plain")},
    )
    assert response.status_code == 400
    assert "video" in response.json()["detail"].lower()


def test_video_upload_invalid_course(auth_client):
    response = auth_client.post(
        "/videos/upload",
        data={"title": "Vid", "course_id": "999"},
        files={"file": ("video.mp4", b"fake", "video/mp4")},
    )
    assert response.status_code == 404


def test_list_videos_empty(auth_client):
    response = auth_client.get("/videos/")
    assert response.status_code == 200
    assert response.json() == []


def test_get_video_not_found(auth_client):
    response = auth_client.get("/videos/999")
    assert response.status_code == 404


def test_upload_video_success(auth_client, tmp_path, monkeypatch):
    course = _create_course(auth_client)
    video, storage = _upload(auth_client, course, tmp_path, monkeypatch)

    assert video["storage_key"].startswith(f"course_videos/{course['id']}/")
    assert video["transcript"] is None
    assert video["file_url"] is None

    stored = list((tmp_path / "course_videos" / str(course["id"])).glob("*.mp4"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == b"fake-video-bytes"


def test_upload_video_with_transcript(auth_client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        videos_router,
        "get_transcription_service",
        lambda: FakeTranscription("Hello world"),
    )
    course = _create_course(auth_client)

    storage = LocalStorageService(base_dir=tmp_path)
    monkeypatch.setattr(videos_router, "get_storage_service", lambda: storage)
    response = auth_client.post(
        "/videos/upload",
        data={
            "title": "Intro",
            "course_id": str(course["id"]),
            "generate_transcript": "true",
        },
        files={"file": ("intro.mp4", b"fake-video-bytes", "video/mp4")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["transcript"] == "Hello world"


def test_upload_video_transcript_fallback(auth_client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        videos_router, "get_transcription_service", lambda: FailingTranscription()
    )
    course = _create_course(auth_client)

    storage = LocalStorageService(base_dir=tmp_path)
    monkeypatch.setattr(videos_router, "get_storage_service", lambda: storage)
    response = auth_client.post(
        "/videos/upload",
        data={
            "title": "Intro",
            "course_id": str(course["id"]),
            "generate_transcript": "true",
        },
        files={"file": ("intro.mp4", b"fake-video-bytes", "video/mp4")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["transcript"] == "Transcription not available"


def test_list_videos_returns_uploaded(auth_client, tmp_path, monkeypatch):
    course = _create_course(auth_client)
    video, _ = _upload(auth_client, course, tmp_path, monkeypatch)

    response = auth_client.get("/videos/")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [video["id"]]


def test_get_video_file_serves_local(auth_client, tmp_path, monkeypatch):
    course = _create_course(auth_client)
    video, _ = _upload(auth_client, course, tmp_path, monkeypatch)

    response = auth_client.get(f"/videos/{video['id']}/file")
    assert response.status_code == 200
    assert response.content == b"fake-video-bytes"


class FakeRemoteStorage:
    """Storage fake with presigned URLs (B2 behavior)."""

    def __init__(self):
        self.files = {}

    async def save(self, key, data, content_type):
        self.files[key] = data

    async def delete(self, key):
        self.files.pop(key, None)

    async def read(self, key):
        return self.files[key]

    def get_url(self, key):
        return f"https://presigned.example.test/{key}"

    def path(self, key):
        return None


def test_get_video_file_redirects_when_remote(auth_client, tmp_path, monkeypatch):
    course = _create_course(auth_client)
    video, storage = _upload(
        auth_client, course, tmp_path, monkeypatch, storage=FakeRemoteStorage()
    )

    response = auth_client.get(f"/videos/{video['id']}/file", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == (
        f"https://presigned.example.test/{video['storage_key']}"
    )


def test_video_delete_removes_file(auth_client, tmp_path, monkeypatch):
    course = _create_course(auth_client)
    video, _ = _upload(auth_client, course, tmp_path, monkeypatch)

    response = auth_client.delete(f"/videos/{video['id']}")
    assert response.status_code == 204
    stored = list((tmp_path / "course_videos" / str(course["id"])).glob("*.mp4"))
    assert stored == []


def test_video_regenerate_transcript(auth_client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        videos_router,
        "get_transcription_service",
        lambda: FakeTranscription("Fresh transcript"),
    )
    course = _create_course(auth_client)
    video, _ = _upload(auth_client, course, tmp_path, monkeypatch)

    response = auth_client.post(f"/videos/{video['id']}/regenerate-transcript")
    assert response.status_code == 200, response.text
    assert response.json()["transcript"] == "Fresh transcript"


def test_video_regenerate_without_api_key(auth_client, tmp_path, monkeypatch):
    def _no_key():
        raise TranscriptionError("GROQ_API_KEY is not configured")

    monkeypatch.setattr(videos_router, "get_transcription_service", _no_key)
    course = _create_course(auth_client)
    video, _ = _upload(auth_client, course, tmp_path, monkeypatch)

    response = auth_client.post(f"/videos/{video['id']}/regenerate-transcript")
    assert response.status_code == 503


class FakeStorage:
    def __init__(self):
        self.saved = {}

    async def save(self, key, data, content_type):
        self.saved[key] = data

    async def delete(self, key):
        self.saved.pop(key, None)

    async def read(self, key):
        return self.saved[key]

    def get_url(self, key):
        return None

    def path(self, key):
        return None


class _ProbeResult:
    stdout = "3.5"


def test_video_service_process_upload_with_duration(monkeypatch):
    storage = FakeStorage()
    monkeypatch.setattr(
        "app.services.video_service.subprocess.run", lambda *a, **k: _ProbeResult()
    )
    result = asyncio.run(
        VideoService(storage, FakeTranscription("summary")).process_upload(
            "course_videos/1/x.mp4", b"bytes", "video/mp4", generate_transcript=True
        )
    )
    assert result["storage_key"] == "course_videos/1/x.mp4"
    assert result["duration"] == 3
    assert result["transcript"] == "summary"
    assert storage.saved["course_videos/1/x.mp4"] == b"bytes"


def test_video_service_transcript_empty_without_transcription():
    storage = FakeStorage()
    result = asyncio.run(
        VideoService(storage, None).process_upload(
            "k.mp4", b"bytes", "video/mp4", generate_transcript=True
        )
    )
    assert result["transcript"] == "Transcription not available"


def test_video_service_regenerate_transcript():
    storage = FakeStorage()
    storage.saved["k.mp4"] = b"data"
    result = asyncio.run(
        VideoService(storage, FakeTranscription("new")).regenerate_transcript("k.mp4")
    )
    assert result == "new"


def test_video_service_transcript_fallback_on_error():
    storage = FakeStorage()
    storage.saved["k.mp4"] = b"data"
    result = asyncio.run(
        VideoService(storage, FailingTranscription()).process_upload(
            "k.mp4", b"bytes", "video/mp4", generate_transcript=True
        )
    )
    assert result["transcript"] == "Transcription not available"


def test_video_service_regenerate_raises_when_storage_read_fails():
    storage = FakeStorage()

    async def _fail_read(key):
        raise UploadError("storage unavailable")

    storage.read = _fail_read
    with pytest.raises(UploadError):
        asyncio.run(
            VideoService(storage, FakeTranscription()).regenerate_transcript("k.mp4")
        )


def test_probe_duration_failure_returns_none(monkeypatch):
    def _boom(cmd, *args, **kwargs):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr("app.services.video_service.subprocess.run", _boom)
    assert VideoService(FakeStorage())._probe_duration(b"data") is None


def test_build_storage_key_format():
    import app.routers.videos as videos_router

    key = videos_router._build_storage_key(course_id=7)
    assert key.startswith("course_videos/7/")
    assert key.endswith(".mp4")


def _make_video_model():
    from datetime import UTC, datetime

    from app.models import Video as VideoModel

    return VideoModel(
        id=1,
        title="Intro",
        course_id=7,
        storage_key="course_videos/7/x.mp4",
        duration=3,
        transcript=None,
        is_synchronized=True,
        created_at=datetime.now(UTC),
    )


def test_to_video_with_local_storage():
    import app.routers.videos as videos_router

    result = videos_router._to_video(_make_video_model(), FakeStorage())
    assert result.file_url is None
    assert result.title == "Intro"


def test_to_video_with_remote_storage():
    import app.routers.videos as videos_router

    result = videos_router._to_video(_make_video_model(), FakeRemoteStorage())
    assert result.file_url == "https://presigned.example.test/course_videos/7/x.mp4"


def test_to_video_with_transcript_remote_storage():
    import app.routers.videos as videos_router

    result = videos_router._to_video_with_transcript(
        _make_video_model(), FakeRemoteStorage()
    )
    assert result.file_url.startswith("https://presigned.example.test/")


class _UrlErrorStorage(FakeStorage):
    def get_url(self, key):
        raise UploadError("url generation failed")


def test_try_get_url_returns_none_on_error():
    import app.routers.videos as videos_router

    assert videos_router._try_get_url(_UrlErrorStorage(), "k.mp4") is None


# --- Direct handler-call tests ----------------------------------------------
# These invoke the handlers in-process (no HTTP), which coverage measures fully.
def _run(fn, *args, **kwargs):
    async def _go():
        async with TestingSessionLocal() as session:
            return await fn(*args, db=session, **kwargs)

    return asyncio.run(_go())


def _create_course_direct() -> int:
    return _run(create_course, CourseCreate(title="Math")).id


def _create_video_direct(course_id: int, storage_key="course_videos/7/x.mp4") -> int:
    async def _go():
        async with TestingSessionLocal() as session:
            video = VideoModel(
                title="Intro", course_id=course_id, storage_key=storage_key
            )
            session.add(video)
            await session.commit()
            await session.refresh(video)
            return video.id

    return asyncio.run(_go())


def test_direct_list_videos_with_filters(monkeypatch):
    course_id = _create_course_direct()
    video_id = _create_video_direct(course_id)
    monkeypatch.setattr(
        videos_router, "get_storage_service", lambda: FakeRemoteStorage()
    )
    videos = _run(get_videos, title="Intro")
    assert len(videos) == 1
    assert videos[0].file_url is not None
    assert [v.id for v in _run(get_videos, course_id=course_id)] == [video_id]


def test_direct_get_video(monkeypatch):
    video_id = _create_video_direct(_create_course_direct())
    monkeypatch.setattr(
        videos_router, "get_storage_service", lambda: FakeRemoteStorage()
    )
    result = _run(get_video, video_id)
    assert result.id == video_id
    assert result.file_url is not None


def test_direct_get_video_not_found():
    with pytest.raises(NotFoundError):
        _run(get_video, 999)


def test_direct_update_video_title(monkeypatch):
    video_id = _create_video_direct(_create_course_direct())
    monkeypatch.setattr(
        videos_router, "get_storage_service", lambda: FakeRemoteStorage()
    )
    updated = _run(update_video, video_id, VideoUpdate(title="Renamed"))
    assert updated.title == "Renamed"


def test_direct_update_video_change_course(monkeypatch):
    course_a = _create_course_direct()
    course_b = _create_course_direct()
    video_id = _create_video_direct(course_a)
    monkeypatch.setattr(
        videos_router, "get_storage_service", lambda: FakeRemoteStorage()
    )
    updated = _run(update_video, video_id, VideoUpdate(course_id=course_b))
    assert updated.course_id == course_b


def test_direct_update_video_invalid_course():
    video_id = _create_video_direct(_create_course_direct())
    with pytest.raises(NotFoundError):
        _run(update_video, video_id, VideoUpdate(course_id=999))


def test_direct_update_video_not_found():
    with pytest.raises(NotFoundError):
        _run(update_video, 999, VideoUpdate(title="X"))


def test_direct_get_video_file_redirects(monkeypatch):
    video_id = _create_video_direct(_create_course_direct())
    monkeypatch.setattr(
        videos_router, "get_storage_service", lambda: FakeRemoteStorage()
    )
    response = _run(get_video_file, video_id)
    assert isinstance(response, RedirectResponse)
    assert response.status_code == 307


def test_direct_get_video_file_local(monkeypatch, tmp_path):
    storage_key = "course_videos/7/local.mp4"
    video_id = _create_video_direct(_create_course_direct(), storage_key=storage_key)
    storage = LocalStorageService(base_dir=tmp_path)
    asyncio.run(storage.save(storage_key, b"content", "video/mp4"))
    monkeypatch.setattr(videos_router, "get_storage_service", lambda: storage)
    response = _run(get_video_file, video_id)
    assert isinstance(response, FileResponse)
    assert response.media_type == "video/mp4"


def test_direct_get_video_file_missing(monkeypatch):
    video_id = _create_video_direct(_create_course_direct())
    monkeypatch.setattr(videos_router, "get_storage_service", lambda: FakeStorage())
    with pytest.raises(HTTPException) as exc_info:
        _run(get_video_file, video_id)
    assert exc_info.value.status_code == 404


def test_direct_delete_video(monkeypatch):
    course_id = _create_course_direct()
    storage_key = "course_videos/7/del.mp4"
    video_id = _create_video_direct(course_id, storage_key=storage_key)
    storage = FakeStorage()
    storage.saved[storage_key] = b"content"
    monkeypatch.setattr(videos_router, "get_storage_service", lambda: storage)
    assert _run(delete_video, video_id) is None


class _DeleteErrorStorage(FakeStorage):
    async def delete(self, key):
        raise UploadError("delete failed")


def test_direct_delete_video_storage_error(monkeypatch):
    video_id = _create_video_direct(_create_course_direct())
    monkeypatch.setattr(
        videos_router, "get_storage_service", lambda: _DeleteErrorStorage()
    )
    with pytest.raises(HTTPException) as exc_info:
        _run(delete_video, video_id)
    assert exc_info.value.status_code == 502


def test_direct_regenerate_transcript(monkeypatch):
    course_id = _create_course_direct()
    storage_key = "course_videos/7/regen.mp4"
    video_id = _create_video_direct(course_id, storage_key=storage_key)
    storage = FakeStorage()
    storage.saved[storage_key] = b"content"
    monkeypatch.setattr(videos_router, "get_storage_service", lambda: storage)
    monkeypatch.setattr(
        videos_router,
        "get_transcription_service",
        lambda: FakeTranscription("Fresh"),
    )
    result = _run(regenerate_transcript, video_id)
    assert result.transcript == "Fresh"


def test_direct_regenerate_transcript_no_key(monkeypatch):
    video_id = _create_video_direct(_create_course_direct())
    monkeypatch.setattr(videos_router, "get_storage_service", lambda: FakeStorage())

    def _no_key():
        raise TranscriptionError("GROQ_API_KEY is not configured")

    monkeypatch.setattr(videos_router, "get_transcription_service", _no_key)
    with pytest.raises(HTTPException) as exc_info:
        _run(regenerate_transcript, video_id)
    assert exc_info.value.status_code == 503


class _ReadErrorStorage(FakeStorage):
    async def read(self, key):
        raise UploadError("read failed")


def test_direct_regenerate_transcript_read_error(monkeypatch):
    course_id = _create_course_direct()
    video_id = _create_video_direct(course_id)
    monkeypatch.setattr(
        videos_router, "get_storage_service", lambda: _ReadErrorStorage()
    )
    monkeypatch.setattr(
        videos_router, "get_transcription_service", lambda: FakeTranscription()
    )
    with pytest.raises(HTTPException) as exc_info:
        _run(regenerate_transcript, video_id)
    assert exc_info.value.status_code == 502
