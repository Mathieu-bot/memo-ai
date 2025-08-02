import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_upload_video():
    with open("test_video.mp4", "rb") as file:
        response = client.post(
            "/videos/upload",
            files={"file": ("test_video.mp4", file, "video/mp4")},
            data={"title": "Test Video", "course_id": "1"}
        )
    assert response.status_code == 201
    assert "id" in response.json()
    assert response.json()["title"] == "Test Video"