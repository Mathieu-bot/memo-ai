def test_generate_quiz_invalid_course(client):
    response = client.post("/ai/generate-quiz/999")
    assert response.status_code == 404


def test_generate_quiz_without_api_key(client):
    course = client.post("/courses/", json={"title": "Math"}).json()
    response = client.post(f"/ai/generate-quiz/{course['id']}")
    assert response.status_code == 503
