from app.auth import UserManager


def test_register(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "new@example.com",
            "password": "password123",
            "username": "bob",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new@example.com"
    assert data["username"] == "bob"
    assert data["is_verified"] is False
    assert "password" not in data


def test_register_duplicate_email(client):
    payload = {
        "email": "dup@example.com",
        "password": "password123",
        "username": "bob",
    }
    assert client.post("/auth/register", json=payload).status_code == 201
    response = client.post(
        "/auth/register",
        json={**payload, "username": "bobby"},
    )
    assert response.status_code == 400


def test_register_duplicate_username(client):
    payload = {
        "email": "one@example.com",
        "password": "password123",
        "username": "alice",
    }
    assert client.post("/auth/register", json=payload).status_code == 201
    response = client.post(
        "/auth/register",
        json={**payload, "email": "two@example.com"},
    )
    assert response.status_code == 400


def test_login_success(client):
    client.post(
        "/auth/register",
        json={
            "email": "login@example.com",
            "password": "password123",
            "username": "carol",
        },
    )
    response = client.post(
        "/auth/login",
        data={"username": "login@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password(client):
    client.post(
        "/auth/register",
        json={
            "email": "login@example.com",
            "password": "password123",
            "username": "carol",
        },
    )
    response = client.post(
        "/auth/login",
        data={"username": "login@example.com", "password": "wrong"},
    )
    assert response.status_code == 400


def test_protected_endpoint_requires_token(client):
    response = client.get("/courses/")
    assert response.status_code == 401


def test_protected_endpoint_requires_verified_user(client):
    client.post(
        "/auth/register",
        json={
            "email": "unverified@example.com",
            "password": "password123",
            "username": "dave",
        },
    )
    login = client.post(
        "/auth/login",
        data={"username": "unverified@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    response = client.get(
        "/courses/",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert response.status_code == 403


def test_users_me(auth_client):
    response = auth_client.get("/users/me")
    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
    assert response.json()["username"] == "alice"


def test_verify_flow(client, monkeypatch):
    tokens = []

    async def fake_hook(self, user, token, request=None):
        tokens.append(token)

    monkeypatch.setattr(UserManager, "on_after_request_verify", fake_hook)
    client.post(
        "/auth/register",
        json={
            "email": "verify@example.com",
            "password": "password123",
            "username": "erin",
        },
    )

    response = client.post(
        "/auth/request-verify-token", json={"email": "verify@example.com"}
    )
    assert response.status_code == 202
    assert len(tokens) == 1

    response = client.post("/auth/verify", json={"token": tokens[0]})
    assert response.status_code == 200
    assert response.json()["is_verified"] is True
