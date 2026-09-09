import asyncio

import pytest

from app.exceptions import NotFoundError
from app.routers.courses import create_course
from app.routers.quizzes import (
    create_quiz,
    delete_quiz,
    get_quiz,
    get_quizzes,
    update_quiz,
)
from app.schemas import CourseCreate, QuizCreate, QuizUpdate
from tests.conftest import TestingSessionLocal


def _create_course(client, title="Math"):
    return client.post("/courses/", json={"title": title}).json()


def test_create_quiz(auth_client):
    course = _create_course(auth_client)
    response = auth_client.post(
        "/quizzes/",
        json={
            "title": "Quiz 1",
            "description": "First quiz",
            "course_id": course["id"],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Quiz 1"
    assert data["course_id"] == course["id"]


def test_create_quiz_invalid_course(auth_client):
    response = auth_client.post("/quizzes/", json={"title": "Q", "course_id": 999})
    assert response.status_code == 404


def test_list_quizzes(auth_client):
    course = _create_course(auth_client)
    auth_client.post("/quizzes/", json={"title": "Q1", "course_id": course["id"]})
    response = auth_client.get("/quizzes/")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_quiz_with_questions(auth_client):
    course = _create_course(auth_client)
    quiz = auth_client.post(
        "/quizzes/", json={"title": "Q", "course_id": course["id"]}
    ).json()
    response = auth_client.get(f"/quizzes/{quiz['id']}")
    assert response.status_code == 200
    assert response.json()["questions"] == []


def test_get_quiz_not_found(auth_client):
    response = auth_client.get("/quizzes/999")
    assert response.status_code == 404


def test_update_quiz(auth_client):
    course = _create_course(auth_client)
    quiz = auth_client.post(
        "/quizzes/", json={"title": "Old", "course_id": course["id"]}
    ).json()
    response = auth_client.put(f"/quizzes/{quiz['id']}", json={"title": "New"})
    assert response.status_code == 200
    assert response.json()["title"] == "New"


def test_delete_quiz(auth_client):
    course = _create_course(auth_client)
    quiz = auth_client.post(
        "/quizzes/", json={"title": "DeleteMe", "course_id": course["id"]}
    ).json()
    response = auth_client.delete(f"/quizzes/{quiz['id']}")
    assert response.status_code == 204
    assert auth_client.get(f"/quizzes/{quiz['id']}").status_code == 404


# --- Direct handler-call tests ----------------------------------------------
# These invoke the handlers in-process (no HTTP), which coverage measures fully.
def _run(fn, *args, **kwargs):
    async def _go():
        async with TestingSessionLocal() as session:
            return await fn(*args, db=session, **kwargs)

    return asyncio.run(_go())


def _create_course_direct() -> int:
    return _run(create_course, CourseCreate(title="Math")).id


def test_direct_list_quizzes():
    _run(create_quiz, QuizCreate(title="Q1", course_id=_create_course_direct()))
    quizzes = _run(get_quizzes)
    assert len(quizzes) == 1


def test_direct_create_quiz():
    quiz = _run(create_quiz, QuizCreate(title="Q1", course_id=_create_course_direct()))
    assert quiz.title == "Q1"
    assert quiz.id is not None


def test_direct_create_quiz_invalid_course():
    with pytest.raises(NotFoundError):
        _run(create_quiz, QuizCreate(title="Q1", course_id=999))


def test_direct_get_quiz():
    quiz = _run(create_quiz, QuizCreate(title="Q1", course_id=_create_course_direct()))
    fetched = _run(get_quiz, quiz.id)
    assert fetched.id == quiz.id
    assert fetched.questions == []


def test_direct_get_quiz_not_found():
    with pytest.raises(NotFoundError):
        _run(get_quiz, 999)


def test_direct_update_quiz():
    quiz = _run(create_quiz, QuizCreate(title="Old", course_id=_create_course_direct()))
    updated = _run(update_quiz, quiz.id, QuizUpdate(title="New"))
    assert updated.title == "New"


def test_direct_update_quiz_not_found():
    with pytest.raises(NotFoundError):
        _run(update_quiz, 999, QuizUpdate(title="New"))


def test_direct_update_quiz_change_course():
    course_a = _create_course_direct()
    course_b = _create_course_direct()
    quiz = _run(create_quiz, QuizCreate(title="Q", course_id=course_a))
    updated = _run(update_quiz, quiz.id, QuizUpdate(course_id=course_b))
    assert updated.course_id == course_b


def test_direct_update_quiz_invalid_course():
    quiz = _run(create_quiz, QuizCreate(title="Q", course_id=_create_course_direct()))
    with pytest.raises(NotFoundError):
        _run(update_quiz, quiz.id, QuizUpdate(course_id=999))


def test_direct_delete_quiz():
    quiz = _run(create_quiz, QuizCreate(title="Q", course_id=_create_course_direct()))
    assert _run(delete_quiz, quiz.id) is None
    with pytest.raises(NotFoundError):
        _run(get_quiz, quiz.id)


def test_direct_delete_quiz_not_found():
    with pytest.raises(NotFoundError):
        _run(delete_quiz, 999)
