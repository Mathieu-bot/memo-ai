def _create_note(client, generate_summary=False, title="Note"):
    course = client.post("/courses/", json={"title": "Math"}).json()
    response = client.post(
        f"/notes/?generate_summary={str(generate_summary).lower()}",
        json={"title": title, "content": "Some content", "course_id": course["id"]},
    )
    return response, course


def test_create_note_without_ai(client):
    response, _ = _create_note(client)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Note"
    assert data["summary"] is None


def test_create_note_with_ai(client):
    response, _ = _create_note(client, generate_summary=True)
    assert response.status_code == 201


def test_create_note_invalid_course(client):
    response = client.post(
        "/notes/", json={"title": "N", "content": "c", "course_id": 999}
    )
    assert response.status_code == 404


def test_get_note(client):
    response, _ = _create_note(client)
    note_id = response.json()["id"]
    r = client.get(f"/notes/{note_id}")
    assert r.status_code == 200
    assert r.json()["id"] == note_id


def test_get_note_not_found(client):
    response = client.get("/notes/999")
    assert response.status_code == 404


def test_filter_notes_by_title(client):
    _create_note(client, title="Python")
    _create_note(client, title="Rust")
    response = client.get("/notes/", params={"title": "Python"})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Python"


def test_update_note(client):
    response, _ = _create_note(client)
    note_id = response.json()["id"]
    r = client.put(f"/notes/{note_id}", json={"title": "Updated"})
    assert r.status_code == 200
    assert r.json()["title"] == "Updated"


def test_delete_note(client):
    response, _ = _create_note(client)
    note_id = response.json()["id"]
    assert client.delete(f"/notes/{note_id}").status_code == 204
    assert client.get(f"/notes/{note_id}").status_code == 404
