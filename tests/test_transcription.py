import os
import subprocess
from io import BytesIO
from pathlib import Path

import pytest

import app.services.ai.transcription_service as transcription_service
from app.exceptions import TranscriptionError
from app.services.ai import get_transcription_service
from app.services.ai.transcription_service import TranscriptionService


class _TranscriptionResult:
    def __init__(self, text: str):
        self.text = text


def _make_fake_groq(api_key: str, *, text: str = "hello", fail: bool = False):
    class FakeGroq:
        def __init__(self, api_key: str):
            self.api_key = api_key
            self._audio = _AudioGateway(text=text, fail=fail)

        @property
        def audio(self):
            return self._audio

    class _AudioGateway:
        def __init__(self, *, text, fail):
            self._transcriptions = _Transcriptions(text=text, fail=fail)

        @property
        def transcriptions(self):
            return self._transcriptions

    class _Transcriptions:
        def __init__(self, *, text, fail):
            self._text = text
            self._fail = fail

        def create(self, **kwargs):
            if self._fail:
                raise RuntimeError("groq unavailable")
            return _TranscriptionResult(self._text)

    return FakeGroq(api_key)


class _ProcResult:
    def __init__(self, stdout: str = ""):
        self.stdout = stdout


@pytest.fixture
def mock_groq(monkeypatch):
    monkeypatch.setattr(
        transcription_service,
        "Groq",
        lambda api_key, **kwargs: _make_fake_groq(api_key, **kwargs),
    )


def test_transcribe_file_success(mock_groq):
    service = TranscriptionService(api_key="k")
    assert service.transcribe_file(BytesIO(b"fake mp4 bytes")) == "hello"


def test_transcribe_path_small_file(mock_groq, tmp_path):
    file_path = tmp_path / "a.mp4"
    file_path.write_bytes(b"data")
    service = TranscriptionService("k")
    assert service.transcribe_path(str(file_path)) == "hello"


def test_transcribe_path_large_file_splits_into_chunks(
    mock_groq, monkeypatch, tmp_path
):
    file_path = tmp_path / "big.mp4"
    file_path.write_bytes(b"x")
    real_getsize = os.path.getsize
    monkeypatch.setattr(
        os.path,
        "getsize",
        lambda path: (
            30 * 1024 * 1024 if str(path).endswith(".mp4") else real_getsize(path)
        ),
    )

    def fake_subprocess_run(cmd, *args, **kwargs):
        if cmd[0] == "ffprobe":
            return _ProcResult(stdout="20.0")
        if cmd[0] == "ffmpeg":
            Path(cmd[-1]).write_bytes(b"segment")
            return _ProcResult()
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(transcription_service.subprocess, "run", fake_subprocess_run)
    service = TranscriptionService("k")
    result = service.transcribe_path(str(file_path))
    assert result == "hello\nhello"


def test_transcribe_path_raises_when_groq_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(
        transcription_service,
        "Groq",
        lambda api_key: _make_fake_groq(api_key, fail=True),
    )
    file_path = tmp_path / "a.mp4"
    file_path.write_bytes(b"data")
    service = TranscriptionService("k")
    with pytest.raises(TranscriptionError):
        service.transcribe_path(str(file_path))


def test_get_duration_returns_none_on_subprocess_error(monkeypatch, tmp_path):
    file_path = tmp_path / "a.mp4"
    file_path.write_bytes(b"data")

    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(transcription_service.subprocess, "run", fake_run)
    service = TranscriptionService("k")
    assert service._get_duration(str(file_path)) is None


def test_get_duration_returns_none_on_invalid_output(monkeypatch, tmp_path):
    file_path = tmp_path / "a.mp4"
    file_path.write_bytes(b"data")
    monkeypatch.setattr(
        transcription_service.subprocess,
        "run",
        lambda cmd, **kwargs: _ProcResult(stdout="not-a-number"),
    )
    service = TranscriptionService("k")
    assert service._get_duration(str(file_path)) is None


def test_split_audio_raises_when_duration_unknown(monkeypatch, tmp_path):
    file_path = tmp_path / "a.mp4"
    file_path.write_bytes(b"data")

    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(transcription_service.subprocess, "run", fake_run)
    service = TranscriptionService("k")
    with pytest.raises(TranscriptionError, match="Could not determine audio duration"):
        service._split_audio(str(file_path), str(tmp_path / "chunks"))


def test_split_audio_raises_when_ffmpeg_fails(monkeypatch, tmp_path):
    file_path = tmp_path / "a.mp4"
    file_path.write_bytes(b"data")
    real_getsize = os.path.getsize
    monkeypatch.setattr(
        os.path,
        "getsize",
        lambda path: (
            30 * 1024 * 1024 if str(path).endswith(".mp4") else real_getsize(path)
        ),
    )

    def fake_run(cmd, **kwargs):
        if cmd[0] == "ffprobe":
            return _ProcResult(stdout="20.0")
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(transcription_service.subprocess, "run", fake_run)
    service = TranscriptionService("k")
    with pytest.raises(TranscriptionError):
        service._split_audio(str(file_path), str(tmp_path / "chunks"))


def test_estimate_segment_duration_defaults(tmp_path):
    service = TranscriptionService("k")
    file_path = tmp_path / "a.mp4"
    file_path.write_bytes(b"x")
    assert service._estimate_segment_duration(str(file_path), total_duration=0) == 300
    assert (
        service._estimate_segment_duration(str(file_path), total_duration=0.001) == 10
    )


class _NoKeySettings:
    GROQ_API_KEY = ""


class _WithKeySettings:
    GROQ_API_KEY = "gsk-test"


def test_get_transcription_service_requires_key(monkeypatch):
    monkeypatch.setattr(transcription_service, "get_settings", lambda: _NoKeySettings())
    with pytest.raises(TranscriptionError):
        get_transcription_service()


def test_get_transcription_service_returns_service(monkeypatch):
    monkeypatch.setattr(
        transcription_service, "get_settings", lambda: _WithKeySettings()
    )
    service = get_transcription_service()
    assert isinstance(service, TranscriptionService)
