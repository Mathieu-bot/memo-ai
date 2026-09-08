def test_video_upload_rejects_non_video(client):
    course = client.post("/courses/", json={"title": "Math"}).json()
    response = client.post(
        "/videos/upload",
        data={"title": "Vid", "course_id": str(course["id"])},
        files={"file": ("notes.txt", b"not a video", "text/plain")},
    )
    assert response.status_code == 400
    assert "video" in response.json()["detail"].lower()


def test_video_upload_invalid_course(client):
    response = client.post(
        "/videos/upload",
        data={"title": "Vid", "course_id": "999"},
        files={"file": ("video.mp4", b"fake", "video/mp4")},
    )
    assert response.status_code == 404


def test_list_videos_empty(client):
    response = client.get("/videos/")
    assert response.status_code == 200
    assert response.json() == []


def test_get_video_not_found(client):
    response = client.get("/videos/999")
    assert response.status_code == 404
