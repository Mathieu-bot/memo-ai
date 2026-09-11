import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.exceptions import AIServiceError, NotFoundError
from app.routers.courses import create_course
from app.routers.notes import (
    create_note,
    delete_note,
    generate_flashcards,
    get_note,
    get_notes,
    summarize_note,
    update_note,
)
from app.schemas import CourseCreate, NoteCreate, NoteUpdate
from tests.conftest import TestingSessionLocal, _db_user

MISSING_ID = "00000000-0000-0000-0000-000000000000"


def _create_note(auth_client, generate_summary=False, title="Note"):
    course = auth_client.post("/courses/", json={"title": "Math"}).json()
    response = auth_client.post(
        f"/notes/?generate_summary={str(generate_summary).lower()}",
        json={"title": title, "content": "Some content", "course_id": course["id"]},
    )
    return response, course


def test_create_note_without_ai(auth_client):
    response, _ = _create_note(auth_client)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Note"
    assert data["summary"] is None


def test_create_note_with_ai(auth_client):
    response, _ = _create_note(auth_client, generate_summary=True)
    assert response.status_code == 201


def test_create_note_invalid_course(auth_client):
    response = auth_client.post(
        "/notes/", json={"title": "N", "content": "c", "course_id": MISSING_ID}
    )
    assert response.status_code == 404


def test_get_note(auth_client):
    response, _ = _create_note(auth_client)
    note_id = response.json()["id"]
    r = auth_client.get(f"/notes/{note_id}")
    assert r.status_code == 200
    assert r.json()["id"] == note_id


def test_get_note_not_found(auth_client):
    response = auth_client.get(f"/notes/{MISSING_ID}")
    assert response.status_code == 404


def test_filter_notes_by_title(auth_client):
    _create_note(auth_client, title="Python")
    _create_note(auth_client, title="Rust")
    response = auth_client.get("/notes/", params={"title": "Python"})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Python"


def test_update_note(auth_client):
    response, _ = _create_note(auth_client)
    note_id = response.json()["id"]
    r = auth_client.put(f"/notes/{note_id}", json={"title": "Updated"})
    assert r.status_code == 200
    assert r.json()["title"] == "Updated"


def test_delete_note(auth_client):
    response, _ = _create_note(auth_client)
    note_id = response.json()["id"]
    assert auth_client.delete(f"/notes/{note_id}").status_code == 204
    assert auth_client.get(f"/notes/{note_id}").status_code == 404


# --- Direct handler-call tests ----------------------------------------------
# These invoke the handlers in-process (no HTTP), which coverage measures fully.
class FakeProvider:
    async def generate_text(self, prompt, system_prompt=""):
        return "AI summary"

    async def generate_structured_json(self, prompt, system_prompt=""):
        return {"flashcards": [{"front": "Front", "back": "Back"}]}


class FailingProvider:
    async def generate_text(self, prompt, system_prompt=""):
        raise AIServiceError("down")

    async def generate_structured_json(self, prompt, system_prompt=""):
        raise AIServiceError("down")


def _run(fn, *args, **kwargs):
    async def _go():
        async with TestingSessionLocal() as session:
            return await fn(*args, db=session, **kwargs)

    return asyncio.run(_go())


def _create_course_direct(user):
    return _run(create_course, CourseCreate(title="Math"), user=user).id


def _create_note_direct(user, course_id, title="Note", content="Content"):
    note = _run(
        create_note,
        NoteCreate(title=title, content=content, course_id=course_id),
        user=user,
    )
    return note.id


def test_direct_list_notes():
    user = _db_user()
    course_id = _create_course_direct(user)
    _create_note_direct(user, course_id, title="Python")
    notes = _run(get_notes, user=user)
    assert [n.title for n in notes] == ["Python"]


def test_direct_filter_notes_by_title_and_course():
    user = _db_user()
    course_a = _create_course_direct(user)
    course_b = _create_course_direct(user)
    _create_note_direct(user, course_a, title="Python")
    _create_note_direct(user, course_b, title="Rust")
    assert [n.title for n in _run(get_notes, user=user, title="Python")] == ["Python"]
    assert [n.title for n in _run(get_notes, user=user, course_id=course_b)] == ["Rust"]


def test_direct_create_note_without_ai(monkeypatch):
    user = _db_user()
    course_id = _create_course_direct(user)

    def _no_key():
        raise AIServiceError("no key")

    monkeypatch.setattr("app.routers.notes.get_ai_provider", _no_key)
    note = _run(
        create_note,
        NoteCreate(title="T", content="C", course_id=course_id),
        user=user,
        generate_summary=True,
    )
    assert note.summary is None


def test_direct_create_note_with_ai(monkeypatch):
    user = _db_user()
    course_id = _create_course_direct(user)
    monkeypatch.setattr("app.routers.notes.get_ai_provider", lambda: FakeProvider())
    note = _run(
        create_note,
        NoteCreate(title="T", content="C", course_id=course_id),
        user=user,
        generate_summary=True,
    )
    assert note.summary == "AI summary"


def test_direct_create_note_invalid_course():
    with pytest.raises(NotFoundError):
        _run(
            create_note,
            NoteCreate(title="T", content="C", course_id=uuid4()),
            user=_db_user(),
        )


def test_direct_get_note():
    user = _db_user()
    course_id = _create_course_direct(user)
    note_id = _create_note_direct(user, course_id)
    assert _run(get_note, note_id, user=user).id == note_id


def test_direct_get_note_not_found():
    with pytest.raises(NotFoundError):
        _run(get_note, uuid4(), user=_db_user())


def test_direct_update_note_title(monkeypatch):
    user = _db_user()
    course_id = _create_course_direct(user)
    note_id = _create_note_direct(user, course_id)
    monkeypatch.setattr("app.routers.notes.get_ai_provider", lambda: FakeProvider())
    updated = _run(update_note, note_id, NoteUpdate(title="Renamed"), user=user)
    assert updated.title == "Renamed"


def test_direct_update_note_regenerates_summary_on_content_change(monkeypatch):
    user = _db_user()
    course_id = _create_course_direct(user)
    note_id = _create_note_direct(user, course_id)
    monkeypatch.setattr("app.routers.notes.get_ai_provider", lambda: FakeProvider())
    updated = _run(update_note, note_id, NoteUpdate(content="New content"), user=user)
    assert updated.summary == "AI summary"


def test_direct_update_note_not_found():
    with pytest.raises(NotFoundError):
        _run(update_note, uuid4(), NoteUpdate(title="X"), user=_db_user())


def test_direct_update_note_invalid_course():
    user = _db_user()
    course_id = _create_course_direct(user)
    note_id = _create_note_direct(user, course_id)
    with pytest.raises(NotFoundError):
        _run(update_note, note_id, NoteUpdate(course_id=uuid4()), user=user)


def test_direct_delete_note():
    user = _db_user()
    course_id = _create_course_direct(user)
    note_id = _create_note_direct(user, course_id)
    assert _run(delete_note, note_id, user=user) is None
    with pytest.raises(NotFoundError):
        _run(get_note, note_id, user=user)


def test_direct_delete_note_not_found():
    with pytest.raises(NotFoundError):
        _run(delete_note, uuid4(), user=_db_user())


def test_direct_summarize_note(monkeypatch):
    user = _db_user()
    course_id = _create_course_direct(user)
    note_id = _create_note_direct(user, course_id)
    monkeypatch.setattr("app.routers.notes.get_ai_provider", lambda: FakeProvider())
    note = _run(summarize_note, note_id, user=user)
    assert note.summary == "AI summary"


def test_direct_summarize_note_ai_failure(monkeypatch):
    user = _db_user()
    course_id = _create_course_direct(user)
    note_id = _create_note_direct(user, course_id)
    monkeypatch.setattr("app.routers.notes.get_ai_provider", lambda: FailingProvider())
    with pytest.raises(HTTPException) as exc_info:
        _run(summarize_note, note_id, user=user)
    assert exc_info.value.status_code == 503


def test_direct_generate_flashcards(monkeypatch):
    user = _db_user()
    course_id = _create_course_direct(user)
    note_id = _create_note_direct(user, course_id)
    monkeypatch.setattr("app.routers.notes.get_ai_provider", lambda: FakeProvider())
    result = _run(generate_flashcards, note_id, user=user, num_cards=2)
    assert result["flashcards"] == [{"front": "Front", "back": "Back"}]
    assert result["note_id"] == note_id


def test_direct_generate_flashcards_ai_failure(monkeypatch):
    user = _db_user()
    course_id = _create_course_direct(user)
    note_id = _create_note_direct(user, course_id)
    monkeypatch.setattr("app.routers.notes.get_ai_provider", lambda: FailingProvider())
    with pytest.raises(HTTPException) as exc_info:
        _run(generate_flashcards, note_id, user=user)
    assert exc_info.value.status_code == 503
