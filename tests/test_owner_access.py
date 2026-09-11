import asyncio
from uuid import UUID

from sqlalchemy import select, update

from app.models import Course as CourseModel
from app.models import User
from tests.conftest import TestingSessionLocal

MISSING_ID = "00000000-0000-0000-0000-000000000000"


def _login_headers(client, email, username, password="password123"):
    """Register + verify + login a user, returning the auth headers."""
    response = client.post(
        "/auth/register",
        json={"email": email, "password": password, "username": username},
    )
    assert response.status_code == 201, response.text
    user_id = UUID(response.json()["id"])

    async def _verify():
        async with TestingSessionLocal() as session:
            await session.execute(
                update(User).where(User.id == user_id).values(is_verified=True)
            )
            await session.commit()

    asyncio.run(_verify())

    login = client.post("/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_owned_article(auth_client):
    """Alice creates a course with a note and a quiz."""
    course = auth_client.post("/courses/", json={"title": "Alice's"}).json()
    note = auth_client.post(
        "/notes/",
        json={
            "title": "Secret note",
            "content": "Content",
            "course_id": course["id"],
        },
        params={"generate_summary": "false"},
    ).json()
    quiz = auth_client.post(
        "/quizzes/",
        json={"title": "Secret quiz", "course_id": course["id"]},
    ).json()
    return course, note, quiz


def test_foreign_course_hidden(auth_client):
    course, _, _ = _create_owned_article(auth_client)
    bob = _login_headers(auth_client, "bob@example.com", "bob")

    assert auth_client.get(f"/courses/{course['id']}", headers=bob).status_code == 404
    assert (
        auth_client.put(
            f"/courses/{course['id']}", json={"title": "Hijacked"}, headers=bob
        ).status_code
        == 404
    )
    assert (
        auth_client.delete(f"/courses/{course['id']}", headers=bob).status_code == 404
    )
    # Missing id stays 404 for everyone.
    assert auth_client.get(f"/courses/{MISSING_ID}", headers=bob).status_code == 404


def test_foreign_note_hidden(auth_client):
    _, note, _ = _create_owned_article(auth_client)
    bob = _login_headers(auth_client, "bob@example.com", "bob")

    assert auth_client.get(f"/notes/{note['id']}", headers=bob).status_code == 404
    assert (
        auth_client.put(
            f"/notes/{note['id']}", json={"title": "Hijacked"}, headers=bob
        ).status_code
        == 404
    )
    assert auth_client.delete(f"/notes/{note['id']}", headers=bob).status_code == 404
    assert (
        auth_client.post(f"/notes/{note['id']}/summarize", headers=bob).status_code
        == 404
    )


def test_foreign_quiz_hidden(auth_client):
    _, _, quiz = _create_owned_article(auth_client)
    bob = _login_headers(auth_client, "bob@example.com", "bob")

    assert auth_client.get(f"/quizzes/{quiz['id']}", headers=bob).status_code == 404
    assert (
        auth_client.put(
            f"/quizzes/{quiz['id']}", json={"title": "Hijacked"}, headers=bob
        ).status_code
        == 404
    )
    assert auth_client.delete(f"/quizzes/{quiz['id']}", headers=bob).status_code == 404


def test_foreign_video_hidden(auth_client, tmp_path, monkeypatch):
    import app.routers.videos as videos_router
    from app.services.storage import LocalStorageService

    course = auth_client.post("/courses/", json={"title": "Alice's"}).json()
    storage = LocalStorageService(base_dir=tmp_path)
    monkeypatch.setattr(videos_router, "get_storage_service", lambda: storage)
    video = auth_client.post(
        "/videos/upload",
        data={
            "title": "Secret video",
            "course_id": str(course["id"]),
            "generate_transcript": "false",
        },
        files={"file": ("intro.mp4", b"fake-video-bytes", "video/mp4")},
    ).json()

    bob = _login_headers(auth_client, "bob@example.com", "bob")
    assert auth_client.get(f"/videos/{video['id']}", headers=bob).status_code == 404
    assert (
        auth_client.put(
            f"/videos/{video['id']}", json={"title": "Hijacked"}, headers=bob
        ).status_code
        == 404
    )
    assert auth_client.delete(f"/videos/{video['id']}", headers=bob).status_code == 404
    # Upload to someone else's course is a 404 too (no leakage).
    assert (
        auth_client.post(
            "/videos/upload",
            data={"title": "X", "course_id": str(course["id"])},
            files={"file": ("x.mp4", b"x", "video/mp4")},
            headers=bob,
        ).status_code
        == 404
    )


def test_lists_are_isolated(auth_client):
    course, note, quiz = _create_owned_article(auth_client)
    bob = _login_headers(auth_client, "bob@example.com", "bob")

    assert auth_client.get("/courses/", headers=bob).json() == []
    assert auth_client.get("/notes/", headers=bob).json() == []
    assert auth_client.get("/quizzes/", headers=bob).json() == []
    assert auth_client.get("/videos/", headers=bob).json() == []

    # Alice still sees her resources.
    assert [c["id"] for c in auth_client.get("/courses/").json()] == [course["id"]]
    assert [n["id"] for n in auth_client.get("/notes/").json()] == [note["id"]]
    assert [q["id"] for q in auth_client.get("/quizzes/").json()] == [quiz["id"]]


def test_create_notes_and_quizzes_require_owned_course(auth_client):
    course = auth_client.post("/courses/", json={"title": "Alice's"}).json()
    bob = _login_headers(auth_client, "bob@example.com", "bob")

    note_response = auth_client.post(
        "/notes/",
        json={"title": "N", "content": "C", "course_id": course["id"]},
        headers=bob,
    )
    assert note_response.status_code == 404

    quiz_response = auth_client.post(
        "/quizzes/",
        json={"title": "Q", "course_id": course["id"]},
        headers=bob,
    )
    assert quiz_response.status_code == 404

    ai_response = auth_client.post(f"/ai/generate-quiz/{course['id']}", headers=bob)
    assert ai_response.status_code == 404


def test_owner_id_set_on_create(auth_client):
    from uuid import UUID

    created = auth_client.post("/courses/", json={"title": "Math"}).json()

    async def _fetch_owner():
        async with TestingSessionLocal() as session:
            result = await session.execute(
                select(CourseModel).where(CourseModel.id == UUID(created["id"]))
            )
            owner = await session.execute(
                select(User).where(User.email == "user@example.com")
            )
            course = result.scalar_one()
            return course.owner_id, owner.scalar_one().id

    course_owner_id, alice_id = asyncio.run(_fetch_owner())
    assert course_owner_id == alice_id
