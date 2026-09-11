import asyncio
from uuid import uuid4

import pytest

from app.exceptions import NotFoundError
from app.routers.courses import (
    create_course,
    delete_course,
    get_course,
    get_courses,
    update_course,
)
from app.schemas import CourseCreate, CourseUpdate
from tests.conftest import TestingSessionLocal, _db_user

MISSING_ID = "00000000-0000-0000-0000-000000000000"


def test_list_courses_empty(auth_client):
    response = auth_client.get("/courses/")
    assert response.status_code == 200
    assert response.json() == []


def test_create_course(auth_client):
    response = auth_client.post(
        "/courses/", json={"title": "Math", "description": "Algebra basics"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Math"
    assert data["description"] == "Algebra basics"
    assert "id" in data


def test_create_course_minimal(auth_client):
    response = auth_client.post("/courses/", json={"title": "Physics"})
    assert response.status_code == 201
    assert response.json()["title"] == "Physics"
    assert response.json()["description"] is None


def test_get_course(auth_client):
    created = auth_client.post("/courses/", json={"title": "Math"}).json()
    response = auth_client.get(f"/courses/{created['id']}")
    assert response.status_code == 200
    assert response.json()["title"] == "Math"


def test_get_course_not_found(auth_client):
    response = auth_client.get(f"/courses/{MISSING_ID}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_update_course(auth_client):
    created = auth_client.post("/courses/", json={"title": "Math"}).json()
    response = auth_client.put(
        f"/courses/{created['id']}", json={"title": "Advanced Math"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Advanced Math"


def test_update_course_invalid_course(auth_client):
    response = auth_client.put(f"/courses/{MISSING_ID}", json={"title": "X"})
    assert response.status_code == 404


def test_delete_course(auth_client):
    created = auth_client.post("/courses/", json={"title": "ToDelete"}).json()
    response = auth_client.delete(f"/courses/{created['id']}")
    assert response.status_code == 204
    assert auth_client.get(f"/courses/{created['id']}").status_code == 404


def test_delete_course_not_found(auth_client):
    response = auth_client.delete(f"/courses/{MISSING_ID}")
    assert response.status_code == 404


# --- Direct handler-call tests ----------------------------------------------
# These invoke the handlers in-process (no HTTP), which coverage measures fully.
def _run(fn, *args, **kwargs):
    async def _go():
        async with TestingSessionLocal() as session:
            return await fn(*args, db=session, **kwargs)

    return asyncio.run(_go())


def test_direct_create_course():
    course = _run(
        create_course, CourseCreate(title="Math", description="Basics"), user=_db_user()
    )
    assert course.title == "Math"
    assert course.description == "Basics"
    assert course.id is not None


def test_direct_list_courses():
    user = _db_user()
    _run(create_course, CourseCreate(title="Math"), user=user)
    courses = _run(get_courses, user=user)
    assert [c.title for c in courses] == ["Math"]


def test_direct_get_course():
    user = _db_user()
    created = _run(create_course, CourseCreate(title="Math"), user=user)
    fetched = _run(get_course, created.id, user=user)
    assert fetched.id == created.id


def test_direct_get_course_not_found():
    with pytest.raises(NotFoundError):
        _run(get_course, uuid4(), user=_db_user())


def test_direct_update_course():
    user = _db_user()
    created = _run(create_course, CourseCreate(title="Math"), user=user)
    updated = _run(update_course, created.id, CourseUpdate(title="Advanced"), user=user)
    assert updated.title == "Advanced"
    assert updated.description is None


def test_direct_update_course_not_found():
    with pytest.raises(NotFoundError):
        _run(update_course, uuid4(), CourseUpdate(title="X"), user=_db_user())


def test_direct_delete_course():
    user = _db_user()
    created = _run(create_course, CourseCreate(title="Math"), user=user)
    assert _run(delete_course, created.id, user=user) is None
    with pytest.raises(NotFoundError):
        _run(get_course, created.id, user=user)


def test_direct_delete_course_not_found():
    with pytest.raises(NotFoundError):
        _run(delete_course, uuid4(), user=_db_user())
