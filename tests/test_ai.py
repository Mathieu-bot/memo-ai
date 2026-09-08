def test_generate_quiz_invalid_course(auth_client):
    response = auth_client.post("/ai/generate-quiz/999")
    assert response.status_code == 404


def test_generate_quiz_without_api_key(auth_client):
    course = auth_client.post("/courses/", json={"title": "Math"}).json()
    response = auth_client.post(f"/ai/generate-quiz/{course['id']}")
    assert response.status_code == 503
