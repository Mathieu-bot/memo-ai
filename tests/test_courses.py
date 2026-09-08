def test_list_courses_empty(client):
    response = client.get("/courses/")
    assert response.status_code == 200
    assert response.json() == []


def test_create_course(client):
    response = client.post(
        "/courses/", json={"title": "Math", "description": "Algebra basics"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Math"
    assert data["description"] == "Algebra basics"
    assert "id" in data


def test_create_course_minimal(client):
    response = client.post("/courses/", json={"title": "Physics"})
    assert response.status_code == 201
    assert response.json()["title"] == "Physics"
    assert response.json()["description"] is None


def test_get_course(client):
    created = client.post("/courses/", json={"title": "Math"}).json()
    response = client.get(f"/courses/{created['id']}")
    assert response.status_code == 200
    assert response.json()["title"] == "Math"


def test_get_course_not_found(client):
    response = client.get("/courses/999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_update_course(client):
    created = client.post("/courses/", json={"title": "Math"}).json()
    response = client.put(f"/courses/{created['id']}", json={"title": "Advanced Math"})
    assert response.status_code == 200
    assert response.json()["title"] == "Advanced Math"


def test_update_course_invalid_course(client):
    response = client.put("/courses/999", json={"title": "X"})
    assert response.status_code == 404


def test_delete_course(client):
    created = client.post("/courses/", json={"title": "ToDelete"}).json()
    response = client.delete(f"/courses/{created['id']}")
    assert response.status_code == 204
    assert client.get(f"/courses/{created['id']}").status_code == 404


def test_delete_course_not_found(client):
    response = client.delete("/courses/999")
    assert response.status_code == 404
