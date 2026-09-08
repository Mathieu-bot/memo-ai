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
    response = auth_client.get("/courses/999")
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
    response = auth_client.put("/courses/999", json={"title": "X"})
    assert response.status_code == 404


def test_delete_course(auth_client):
    created = auth_client.post("/courses/", json={"title": "ToDelete"}).json()
    response = auth_client.delete(f"/courses/{created['id']}")
    assert response.status_code == 204
    assert auth_client.get(f"/courses/{created['id']}").status_code == 404


def test_delete_course_not_found(auth_client):
    response = auth_client.delete("/courses/999")
    assert response.status_code == 404
