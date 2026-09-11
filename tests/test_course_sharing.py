import asyncio
from uuid import UUID

from sqlalchemy import update

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
    user_id = response.json()["id"]

    async def _verify():
        async with TestingSessionLocal() as session:
            await session.execute(
                update(User).where(User.id == UUID(user_id)).values(is_verified=True)
            )
            await session.commit()

    asyncio.run(_verify())

    login = client.post("/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, user_id


def _shared_course(auth_client) -> dict:
    """Alice creates a course and shares it with Bob."""
    course = auth_client.post("/courses/", json={"title": "Shared"}).json()
    bob_headers, bob_id = _login_headers(auth_client, "bob@example.com", "bob")
    add = auth_client.post(
        f"/courses/{course['id']}/members",
        json={"user_id": bob_id},
    )
    assert add.status_code == 201, add.text
    return course, bob_headers, bob_id


def test_share_add_and_list_members(auth_client):
    course, _, bob_id = _shared_course(auth_client)

    members = auth_client.get(f"/courses/{course['id']}/members").json()
    roles = {m["role"] for m in members}
    user_ids = {m["user_id"] for m in members}
    assert roles == {"owner", "member"}
    assert len(user_ids) == 2
    assert bob_id in user_ids


def test_member_can_read_shared_course(auth_client):
    course, bob_headers, _ = _shared_course(auth_client)

    # Bob creates a note (as member) is forbidden, but reading is allowed.
    note_response = auth_client.post(
        "/notes/",
        json={"title": "N", "content": "C", "course_id": course["id"]},
        headers=bob_headers,
    )
    assert note_response.status_code == 404

    alice_note = auth_client.post(
        "/notes/",
        json={"title": "Visible note", "content": "C", "course_id": course["id"]},
        params={"generate_summary": "false"},
    ).json()
    alice_quiz = auth_client.post(
        "/quizzes/",
        json={"title": "Visible quiz", "course_id": course["id"]},
    ).json()

    assert (
        auth_client.get(f"/courses/{course['id']}", headers=bob_headers).status_code
        == 200
    )
    assert (
        auth_client.get(f"/notes/{alice_note['id']}", headers=bob_headers).status_code
        == 200
    )
    assert (
        auth_client.get(f"/quizzes/{alice_quiz['id']}", headers=bob_headers).status_code
        == 200
    )
    # The shared course appears in Bob's lists.
    assert [
        c["id"] for c in auth_client.get("/courses/", headers=bob_headers).json()
    ] == [course["id"]]
    assert [
        n["id"] for n in auth_client.get("/notes/", headers=bob_headers).json()
    ] == [alice_note["id"]]


def test_member_cannot_write(auth_client):
    course, bob_headers, _ = _shared_course(auth_client)

    assert (
        auth_client.put(
            f"/courses/{course['id']}", json={"title": "Renamed"}, headers=bob_headers
        ).status_code
        == 404
    )
    assert (
        auth_client.delete(f"/courses/{course['id']}", headers=bob_headers).status_code
        == 404
    )

    note = auth_client.post(
        "/notes/",
        json={"title": "N", "content": "C", "course_id": course["id"]},
        params={"generate_summary": "false"},
    ).json()
    assert (
        auth_client.put(
            f"/notes/{note['id']}", json={"title": "Renamed"}, headers=bob_headers
        ).status_code
        == 404
    )
    assert (
        auth_client.delete(f"/notes/{note['id']}", headers=bob_headers).status_code
        == 404
    )

    quiz = auth_client.post(
        "/quizzes/", json={"title": "Q", "course_id": course["id"]}
    ).json()
    assert (
        auth_client.delete(f"/quizzes/{quiz['id']}", headers=bob_headers).status_code
        == 404
    )


def test_member_cannot_manage_members(auth_client):
    course, bob_headers, _ = _shared_course(auth_client)
    _, charlie_id = _login_headers(auth_client, "charlie@example.com", "charlie")

    add = auth_client.post(
        f"/courses/{course['id']}/members",
        json={"user_id": charlie_id},
        headers=bob_headers,
    )
    assert add.status_code == 404
    assert (
        auth_client.delete(
            f"/courses/{course['id']}/members/{charlie_id}", headers=bob_headers
        ).status_code
        == 404
    )


def test_remove_member_revokes_access(auth_client):
    course, bob_headers, bob_id = _shared_course(auth_client)

    assert (
        auth_client.get(f"/courses/{course['id']}", headers=bob_headers).status_code
        == 200
    )
    removed = auth_client.delete(f"/courses/{course['id']}/members/{bob_id}")
    assert removed.status_code == 204
    assert (
        auth_client.get(f"/courses/{course['id']}", headers=bob_headers).status_code
        == 404
    )


def test_add_member_to_foreign_course_forbidden(auth_client):
    course = auth_client.post("/courses/", json={"title": "Alice's"}).json()
    bob_headers, _ = _login_headers(auth_client, "bob@example.com", "bob")
    _, charlie_id = _login_headers(auth_client, "charlie@example.com", "charlie")

    add = auth_client.post(
        f"/courses/{course['id']}/members",
        json={"user_id": charlie_id},
        headers=bob_headers,
    )
    assert add.status_code == 404


def test_add_member_errors(auth_client):
    course = auth_client.post("/courses/", json={"title": "Alice's"}).json()
    _, bob_id = _login_headers(auth_client, "bob@example.com", "bob")

    # Owner cannot be shared as a member.
    alice_id = auth_client.get("/users/me").json()["id"]
    owner_add = auth_client.post(
        f"/courses/{course['id']}/members", json={"user_id": alice_id}
    )
    assert owner_add.status_code == 400

    # Unknown user.
    missing = auth_client.post(
        f"/courses/{course['id']}/members", json={"user_id": MISSING_ID}
    )
    assert missing.status_code == 404

    # Duplicate member.
    assert (
        auth_client.post(
            f"/courses/{course['id']}/members", json={"user_id": bob_id}
        ).status_code
        == 201
    )
    duplicate = auth_client.post(
        f"/courses/{course['id']}/members", json={"user_id": bob_id}
    )
    assert duplicate.status_code == 409


def test_remove_member_errors(auth_client):
    course = auth_client.post("/courses/", json={"title": "Alice's"}).json()
    _, bob_id = _login_headers(auth_client, "bob@example.com", "bob")

    # Removing a non-member is a 404.
    removed = auth_client.delete(f"/courses/{course['id']}/members/{bob_id}")
    assert removed.status_code == 404
