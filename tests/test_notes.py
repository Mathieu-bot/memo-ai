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
        "/notes/", json={"title": "N", "content": "c", "course_id": 999}
    )
    assert response.status_code == 404


def test_get_note(auth_client):
    response, _ = _create_note(auth_client)
    note_id = response.json()["id"]
    r = auth_client.get(f"/notes/{note_id}")
    assert r.status_code == 200
    assert r.json()["id"] == note_id


def test_get_note_not_found(auth_client):
    response = auth_client.get("/notes/999")
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
