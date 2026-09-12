import asyncio
import inspect
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.exceptions import AIServiceError, NotFoundError
from app.routers.ai import generate_quiz
from app.routers.courses import create_course
from app.schemas import CourseCreate
from app.services.ai import (
    FlashcardService,
    QuizGenerator,
    SummaryService,
)
from app.services.ai.gemini import GeminiProvider, get_ai_provider
from tests.conftest import TestingSessionLocal, _db_user, make_request

MISSING_ID = "00000000-0000-0000-0000-000000000000"


class RecordingProvider:
    """Fake AIProvider that records prompts and returns canned answers."""

    def __init__(self, text="answer", data=None):
        self.text = text
        self.data = (
            data
            if data is not None
            else {"flashcards": [], "title": "", "questions": []}
        )
        self.calls = []

    async def generate_text(self, prompt, system_prompt=""):
        self.calls.append((prompt, system_prompt))
        return self.text

    async def generate_structured_json(self, prompt, system_prompt=""):
        self.calls.append((prompt, system_prompt))
        return self.data


def test_generate_quiz_invalid_course(auth_client):
    response = auth_client.post(f"/ai/generate-quiz/{MISSING_ID}")
    assert response.status_code == 404


def test_generate_quiz_without_api_key(auth_client, monkeypatch):
    def _no_key_provider():
        raise AIServiceError("GEMINI_API_KEY is not configured")

    monkeypatch.setattr("app.routers.ai.get_ai_provider", _no_key_provider)
    course = auth_client.post("/courses/", json={"title": "Math"}).json()
    response = auth_client.post(f"/ai/generate-quiz/{course['id']}")
    assert response.status_code == 503


def test_generate_quiz_invalid_ai_output_returns_502(auth_client, monkeypatch):
    class GarbageProvider:
        async def generate_structured_json(self, prompt, system_prompt=""):
            return "not even a dict"

    monkeypatch.setattr("app.routers.ai.get_ai_provider", lambda: GarbageProvider())
    course = auth_client.post("/courses/", json={"title": "Math"}).json()
    response = auth_client.post(f"/ai/generate-quiz/{course['id']}")
    assert response.status_code == 502


def test_generate_quiz_num_questions_bounds(auth_client, monkeypatch):
    class UnusedProvider:
        async def generate_structured_json(self, prompt, system_prompt=""):
            raise AssertionError("AI must not be called")

    monkeypatch.setattr("app.routers.ai.get_ai_provider", lambda: UnusedProvider())
    course = auth_client.post("/courses/", json={"title": "Math"}).json()
    response = auth_client.post(
        f"/ai/generate-quiz/{course['id']}", params={"num_questions": 0}
    )
    assert response.status_code == 422


def test_summary_uses_grounded_system_prompt():
    provider = RecordingProvider(text="summary")
    result = asyncio.run(SummaryService(provider).summarize("Content X"))
    assert result == "summary"
    _, system_prompt = provider.calls[0]
    assert "ONLY on the provided content" in system_prompt


def test_quiz_uses_grounded_system_prompt():
    provider = RecordingProvider(
        data={"title": "Q", "description": "D", "questions": []}
    )
    asyncio.run(
        QuizGenerator(provider).generate("Title", "Description", num_questions=3)
    )
    _, system_prompt = provider.calls[0]
    assert "ONLY on the provided content" in system_prompt


def test_flashcards_use_grounded_system_prompt():
    provider = RecordingProvider(data={"flashcards": []})
    result = asyncio.run(FlashcardService(provider).generate("Content X", num_cards=5))
    assert result == []
    _, system_prompt = provider.calls[0]
    assert "ONLY on the provided content" in system_prompt


def test_flashcards_return_list_from_payload():
    provider = RecordingProvider(data={"flashcards": [{"front": "Q", "back": "A"}]})
    result = asyncio.run(FlashcardService(provider).generate("Content", num_cards=1))
    assert result == [{"front": "Q", "back": "A"}]


def test_gemini_uses_zero_temperature_for_text_and_json():
    captured = []

    class FakeResponse:
        text = '{"ok": true}'

    class FakeModel:
        async def generate_content(self, **kwargs):
            captured.append(kwargs)
            return FakeResponse()

    class FakeAio:
        models = FakeModel()

    class FakeClient:
        aio = FakeAio()

    provider = GeminiProvider(api_key="dummy", model="gemini-test")
    provider.client = FakeClient()

    text_result = asyncio.run(provider.generate_text("summarize this"))
    json_result = asyncio.run(
        provider.generate_structured_json("json", system_prompt="system")
    )
    assert text_result == '{"ok": true}'
    assert json_result == {"ok": True}
    assert len(captured) == 2
    assert all(call["config"].temperature == 0.0 for call in captured)
    assert captured[1]["config"].system_instruction == "system"


def test_gemini_raises_on_invalid_json():
    class FakeResponse:
        text = "not valid json"

    class FakeModel:
        async def generate_content(self, **kwargs):
            return FakeResponse()

    class FakeAio:
        models = FakeModel()

    class FakeClient:
        aio = FakeAio()

    provider = GeminiProvider(api_key="dummy", model="gemini-test")
    provider.client = FakeClient()

    with pytest.raises(AIServiceError):
        asyncio.run(provider.generate_structured_json("json"))


class _NoKeySettings:
    GEMINI_API_KEY = ""


def test_get_ai_provider_requires_key(monkeypatch):
    monkeypatch.setattr("app.services.ai.gemini.get_settings", lambda: _NoKeySettings())
    with pytest.raises(AIServiceError):
        get_ai_provider()


class _WithKeySettings:
    GEMINI_API_KEY = "test-key"
    GEMINI_MODEL = "gemini-test-model"
    GEMINI_MODELS = []


def test_get_ai_provider_returns_provider(monkeypatch):
    monkeypatch.setattr(
        "app.services.ai.gemini.get_settings", lambda: _WithKeySettings()
    )
    provider = get_ai_provider()
    assert isinstance(provider, GeminiProvider)
    assert provider.model == "gemini-test-model"


class _Response:
    def __init__(self, text="ok"):
        self.text = text


class _FakeClient:
    def __init__(self, model):
        self.aio = _FakeAio(model)


class _FakeAio:
    def __init__(self, model):
        self.models = model


def test_gemini_retries_once_then_succeeds(monkeypatch):
    class FlakyModel:
        def __init__(self):
            self.calls = 0

        async def generate_content(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary failure")
            return _Response(text="recovered")

    provider = GeminiProvider(api_key="k", model="m")
    provider.client = _FakeClient(FlakyModel())
    monkeypatch.setattr("app.services.ai.gemini.asyncio.sleep", lambda delay: _noop())
    assert asyncio.run(provider.generate_text("hi")) == "recovered"


async def _noop():
    return None


def test_gemini_falls_back_to_next_model_when_quota_exhausted(monkeypatch):
    class QuotaError(RuntimeError):
        code = 429
        status = "RESOURCE_EXHAUSTED"
        details = {"error": {"status": "RESOURCE_EXHAUSTED", "message": "quota"}}

    calls = []

    class TwoTierModel:
        async def generate_content(self, model, **kwargs):
            calls.append(model)
            if model == "m1":
                raise QuotaError("quota exceeded")
            return _Response(text="fallback-ok")

    provider = GeminiProvider(api_key="k", model=["m1", "m2"])
    provider.client = _FakeClient(TwoTierModel())
    monkeypatch.setattr("app.services.ai.gemini.asyncio.sleep", lambda delay: _noop())
    result = asyncio.run(provider.generate_text("hi"))
    assert result == "fallback-ok"
    assert calls == ["m1", "m2"]


def test_gemini_retries_then_raises(monkeypatch):
    class AlwaysDown:
        async def generate_content(self, **kwargs):
            raise RuntimeError("down")

    provider = GeminiProvider(api_key="k", model="m")
    provider.client = _FakeClient(AlwaysDown())
    monkeypatch.setattr("app.services.ai.gemini.asyncio.sleep", lambda delay: _noop())
    with pytest.raises(AIServiceError):
        asyncio.run(provider.generate_text("hi"))


def test_gemini_structured_json_returns_dict():
    class JsonResponse:
        text = '{"title": "Q", "questions": []}'

    class JsonModel:
        async def generate_content(self, **kwargs):
            return JsonResponse()

    provider = GeminiProvider(api_key="k", model="m")
    provider.client = _FakeClient(JsonModel())
    result = asyncio.run(provider.generate_structured_json("json"))
    assert result == {"title": "Q", "questions": []}


# --- Direct handler-call tests (coverage measures these fully) --------------
class _QuizProvider:
    async def generate_structured_json(self, prompt, system_prompt=""):
        return {
            "title": "Quiz: Math",
            "description": "D",
            "questions": [
                {
                    "text": "Q1",
                    "explanation": "E",
                    "answers": [
                        {"text": "A", "is_correct": True},
                        {"text": "B", "is_correct": False},
                    ],
                }
            ],
        }


class _EmptyQuizProvider:
    async def generate_structured_json(self, prompt, system_prompt=""):
        return {"title": "", "questions": []}


class _FailingQuizProvider:
    async def generate_structured_json(self, prompt, system_prompt=""):
        raise AIServiceError("down")


def _run(fn, *args, **kwargs):
    async def _go():
        async with TestingSessionLocal() as session:
            call_args = list(args)
            params = list(inspect.signature(fn).parameters)
            if params and params[0] == "request":
                call_args.insert(0, make_request())
            return await fn(*call_args, db=session, **kwargs)

    return asyncio.run(_go())


def _create_course_direct(user):
    return _run(create_course, CourseCreate(title="Math"), user=user).id


def test_direct_generate_quiz_success(monkeypatch):
    user = _db_user()
    course_id = _create_course_direct(user)
    monkeypatch.setattr("app.routers.ai.get_ai_provider", lambda: _QuizProvider())
    result = _run(generate_quiz, course_id, user=user, num_questions=3)
    assert isinstance(result["quiz_id"], UUID)


def test_direct_generate_quiz_invalid_course():
    with pytest.raises(NotFoundError):
        _run(generate_quiz, uuid4(), user=_db_user())


def test_direct_generate_quiz_invalid_structure(monkeypatch):
    user = _db_user()
    course_id = _create_course_direct(user)
    monkeypatch.setattr("app.routers.ai.get_ai_provider", lambda: _EmptyQuizProvider())
    with pytest.raises(HTTPException) as exc_info:
        _run(generate_quiz, course_id, user=user)
    assert exc_info.value.status_code == 502


def test_direct_generate_quiz_ai_failure(monkeypatch):
    user = _db_user()
    course_id = _create_course_direct(user)
    monkeypatch.setattr(
        "app.routers.ai.get_ai_provider", lambda: _FailingQuizProvider()
    )
    with pytest.raises(HTTPException) as exc_info:
        _run(generate_quiz, course_id, user=user)
    assert exc_info.value.status_code == 503
