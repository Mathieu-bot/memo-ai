import asyncio
from uuid import uuid4

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
from tests.conftest import TestingSessionLocal, _db_user

MISSING_ID = "00000000-0000-0000-0000-000000000000"


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
    response = auth_client.post(
        "/quizzes/", json={"title": "Q", "course_id": MISSING_ID}
    )
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
    response = auth_client.get(f"/quizzes/{MISSING_ID}")
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


def _create_course_direct(user):
    return _run(create_course, CourseCreate(title="Math"), user=user).id


def test_direct_list_quizzes():
    user = _db_user()
    _run(
        create_quiz,
        QuizCreate(title="Q1", course_id=_create_course_direct(user)),
        user=user,
    )
    quizzes = _run(get_quizzes, user=user)
    assert len(quizzes) == 1


def test_direct_create_quiz():
    user = _db_user()
    quiz = _run(
        create_quiz,
        QuizCreate(title="Q1", course_id=_create_course_direct(user)),
        user=user,
    )
    assert quiz.title == "Q1"
    assert quiz.id is not None


def test_direct_create_quiz_invalid_course():
    with pytest.raises(NotFoundError):
        _run(create_quiz, QuizCreate(title="Q1", course_id=uuid4()), user=_db_user())


def test_direct_get_quiz():
    user = _db_user()
    quiz = _run(
        create_quiz,
        QuizCreate(title="Q1", course_id=_create_course_direct(user)),
        user=user,
    )
    fetched = _run(get_quiz, quiz.id, user=user)
    assert fetched.id == quiz.id
    assert fetched.questions == []


def test_direct_get_quiz_not_found():
    with pytest.raises(NotFoundError):
        _run(get_quiz, uuid4(), user=_db_user())


def test_direct_update_quiz():
    user = _db_user()
    quiz = _run(
        create_quiz,
        QuizCreate(title="Old", course_id=_create_course_direct(user)),
        user=user,
    )
    updated = _run(update_quiz, quiz.id, QuizUpdate(title="New"), user=user)
    assert updated.title == "New"


def test_direct_update_quiz_not_found():
    with pytest.raises(NotFoundError):
        _run(update_quiz, uuid4(), QuizUpdate(title="New"), user=_db_user())


def test_direct_update_quiz_change_course():
    user = _db_user()
    course_a = _create_course_direct(user)
    course_b = _create_course_direct(user)
    quiz = _run(create_quiz, QuizCreate(title="Q", course_id=course_a), user=user)
    updated = _run(update_quiz, quiz.id, QuizUpdate(course_id=course_b), user=user)
    assert updated.course_id == course_b


def test_direct_update_quiz_invalid_course():
    user = _db_user()
    quiz = _run(
        create_quiz,
        QuizCreate(title="Q", course_id=_create_course_direct(user)),
        user=user,
    )
    with pytest.raises(NotFoundError):
        _run(update_quiz, quiz.id, QuizUpdate(course_id=uuid4()), user=user)


def test_direct_delete_quiz():
    user = _db_user()
    quiz = _run(
        create_quiz,
        QuizCreate(title="Q", course_id=_create_course_direct(user)),
        user=user,
    )
    assert _run(delete_quiz, quiz.id, user=user) is None
    with pytest.raises(NotFoundError):
        _run(get_quiz, quiz.id, user=user)


def test_direct_delete_quiz_not_found():
    with pytest.raises(NotFoundError):
        _run(delete_quiz, uuid4(), user=_db_user())
