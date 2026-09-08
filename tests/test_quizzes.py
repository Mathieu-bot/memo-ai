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
