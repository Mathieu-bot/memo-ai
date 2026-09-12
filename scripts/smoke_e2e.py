"""End-to-end smoke test against a real uvicorn server process.

Spawns the app on a fixed local port with an isolated temp database / upload
dir, then runs 23 HTTP-level checks (auth, verification via emailed token,
CRUD, sharing, uploads, error codes, CORS). Prints a score and exits non-zero
if any check fails.

Usage:  venv/bin/python scripts/smoke_e2e.py
"""

import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1"
PORT = 8123
BASE_URL = f"http://{HOST}:{PORT}"

JWT_SECRET = "smoke-e2e-dev-only-jwt-secret-for-memoai-tests-" + "x" * 40
FAKE_MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00\x00\x00\x00"
VERIFY_TOKEN_RE = re.compile(r"auth/verify\?token=([A-Za-z0-9._-]+)")


class SmokeFailed(Exception):
    pass


def logs_text(logs) -> str:
    return "\n".join(logs)


def _reader(proc, logs):
    for line in proc.stdout:
        logs.append(line.rstrip("\n"))


def check(number, name, fn):
    try:
        fn()
        print(f"  ok  [{number:02d}/23] {name}")
        return True
    except Exception as exc:  # noqa: BLE001 - report and continue
        print(f"FAIL  [{number:02d}/23] {name}: {exc}")
        return False


def _verify_token(logs, index):
    """Nth distinct verification token, in first-seen order."""
    seen = []
    for line in logs:
        for match in VERIFY_TOKEN_RE.findall(line):
            if match not in seen:
                seen.append(match)
    if len(seen) <= index:
        raise AssertionError(f"not enough emailed tokens ({len(seen)})")
    return seen[index]


def _request_verify_email(client, logs, email, index):
    resp = client.post("/auth/request-verify-token", json={"email": email})
    if resp.status_code not in (200, 202):
        raise AssertionError(
            f"request-verify-token {resp.status_code}: {resp.text[:120]}"
        )
    return _verify_token(logs, index)


def _register_verify_login(client, logs, email, username, token_index):
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "username": username},
    )
    if resp.status_code != 201:
        raise AssertionError(f"register {resp.status_code}: {resp.text[:120]}")
    user_id = resp.json()["id"]
    token = _request_verify_email(client, logs, email, token_index)
    resp = client.post("/auth/verify", json={"token": token})
    if resp.status_code != 200:
        raise AssertionError(f"verify {resp.status_code}: {resp.text[:120]}")
    resp = client.post(
        "/auth/login", data={"username": email, "password": "password123"}
    )
    if resp.status_code != 200:
        raise AssertionError(f"login {resp.status_code}: {resp.text[:120]}")
    client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
    return user_id


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="memoai-smoke-") as tmp:
        tmp_path = Path(tmp)
        env = dict(os.environ)
        env.update(
            {
                "JWT_SECRET": JWT_SECRET,
                "DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'smoke.db'}",
                "STORAGE_DIR": str(tmp_path / "uploads"),
                "ENVIRONMENT": "development",
                "PORT": str(PORT),
                "GEMINI_API_KEY": "",
                "RATE_LIMITING_ENABLED": "true",
                "PUBLIC_BASE_URL": BASE_URL,
                "PYTHONPATH": str(REPO_ROOT),
            }
        )
        init = subprocess.run(
            [sys.executable, "init_db.py"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        if init.returncode != 0:
            raise SmokeFailed(f"init_db failed:\n{init.stderr}")

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                HOST,
                "--port",
                str(PORT),
            ],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        logs: list[str] = []
        threading.Thread(target=_reader, args=(proc, logs), daemon=True).start()

        try:
            alice = httpx.Client(base_url=BASE_URL, timeout=30)
            bob = httpx.Client(base_url=BASE_URL, timeout=30)

            deadline = time.time() + 30
            while time.time() < deadline:
                try:
                    if alice.get("/docs").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.5)
            else:
                raise SmokeFailed("server did not become ready")

            results = {}
            results[1] = check(
                1,
                "GET /docs -> 200 (server up)",
                lambda: _http(alice.get("/docs"), 200),
            )
            results[2] = check(2, "CORS preflight -> ACAO header", lambda: _cors(alice))
            results[3] = check(
                3,
                "GET /courses/ without auth -> 401",
                lambda: _http(alice.get("/courses/"), 401),
            )
            results[4] = check(
                4,
                "register alice -> 201",
                lambda: _http(
                    alice.post(
                        "/auth/register",
                        json={
                            "email": "alice@example.com",
                            "password": "password123",
                            "username": "alice",
                        },
                    ),
                    201,
                ),
            )
            results[5] = check(
                5,
                "unverified token cannot access /courses/ -> 403",
                lambda: _unverified_access(alice),
            )
            results[6] = check(
                6,
                "verify alice through emailed token -> 200",
                lambda: _http(
                    alice.post(
                        "/auth/verify",
                        json={
                            "token": _request_verify_email(
                                alice, logs, "alice@example.com", 0
                            )
                        },
                    ),
                    200,
                ),
            )
            results[7] = check(
                7,
                "login alice after verify -> 200 token",
                lambda: _login(alice, "alice@example.com"),
            )
            results[8] = check(
                8,
                "GET /users/me reports alice",
                lambda: _require(
                    lambda: (
                        alice.get("/users/me").json()["email"] == "alice@example.com"
                    )
                ),
            )

            course_id = {}
            results[9] = check(
                9, "POST /courses/ -> 201", lambda: _course_create(alice, course_id)
            )
            results[10] = check(
                10,
                "GET /courses/ contains the course",
                lambda: _require(
                    lambda: (
                        course_id["id"]
                        in [c["id"] for c in alice.get("/courses/").json()]
                    )
                ),
            )
            results[11] = check(
                11,
                "PUT /courses/{id} updates description",
                lambda: _http(
                    alice.put(
                        f"/courses/{course_id['id']}", json={"description": "updated"}
                    ),
                    200,
                ),
            )
            results[12] = check(
                12,
                "share course with its owner -> 400",
                lambda: _http(
                    alice.post(
                        f"/courses/{course_id['id']}/members",
                        json={"user_id": alice.get("/users/me").json()["id"]},
                    ),
                    400,
                ),
            )

            bob_id = {}
            results[13] = check(
                13,
                "register+verify bob, add as member -> 201",
                lambda: _bob_member(alice, bob, logs, course_id, bob_id),
            )
            results[14] = check(
                14,
                "duplicate member -> 409",
                lambda: _http(
                    alice.post(
                        f"/courses/{course_id['id']}/members",
                        json={"user_id": bob_id["id"]},
                    ),
                    409,
                ),
            )

            note_id = {}
            results[15] = check(
                15,
                "POST /notes/ -> 201",
                lambda: _note_create(alice, course_id, note_id),
            )
            results[16] = check(
                16,
                "GET /notes/?limit=0 -> 422",
                lambda: _http(alice.get("/notes/", params={"limit": 0}), 422),
            )
            results[17] = check(
                17,
                "PUT /notes/{id} with null title -> 422",
                lambda: _http(
                    alice.put(f"/notes/{note_id['id']}", json={"title": None}), 422
                ),
            )

            video_id = {}
            results[18] = check(
                18,
                "POST /videos/upload (valid mp4) -> 201",
                lambda: _video_upload(alice, course_id, video_id),
            )
            results[19] = check(
                19,
                "bob can read the shared course video -> 200",
                lambda: _http(bob.get(f"/videos/{video_id['id']}"), 200),
            )
            results[20] = check(
                20,
                "upload with bad magic bytes -> 400",
                lambda: _bad_magic(alice, course_id),
            )

            bob_course = {}
            results[21] = check(
                21,
                "alice cannot access bob's private course -> 404",
                lambda: _bob_private_course(alice, bob, bob_course),
            )
            results[22] = check(
                22,
                "POST /ai/generate-quiz without key -> 503",
                lambda: _http(alice.post(f"/ai/generate-quiz/{course_id['id']}"), 503),
            )
            results[23] = check(
                23,
                "POST /quizzes/ -> 201",
                lambda: _http(
                    alice.post(
                        "/quizzes/", json={"title": "Q", "course_id": course_id["id"]}
                    ),
                    201,
                ),
            )

            passed = sum(results.values())
            print(f"\nSMOKE E2E: {passed}/23 checks passed")
            if passed < 23:
                print("Server log tail:\n" + "\n".join(logs[-15:]))
                return 1
            return 0
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def _http(resp, expected):
    if resp.status_code != expected:
        raise AssertionError(
            f"status {resp.status_code} != {expected} ({resp.text[:120]})"
        )
    return resp


def _require(pred):
    if not pred():
        raise AssertionError("condition not satisfied")
    return True


def _cors(client):
    resp = client.options(
        "/courses/",
        headers={
            "Origin": "https://app.example.test",
            "Access-Control-Request-Method": "POST",
        },
    )
    if "access-control-allow-origin" not in resp.headers:
        raise AssertionError("missing Access-Control-Allow-Origin")
    return resp


def _login(client, email):
    resp = client.post(
        "/auth/login", data={"username": email, "password": "password123"}
    )
    if resp.status_code != 200:
        raise AssertionError(f"login {resp.status_code}: {resp.text[:120]}")
    client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
    return resp


def _unverified_access(client):
    _login(client, "alice@example.com")
    resp = client.get("/courses/")
    if resp.status_code != 403:
        body = resp.text[:120]
        raise AssertionError(
            f"expected 403 for unverified access, got {resp.status_code} ({body})"
        )
    client.headers.pop("Authorization", None)
    return resp


def _course_create(client, store):
    resp = client.post("/courses/", json={"title": "Math"})
    if resp.status_code != 201:
        raise AssertionError(f"{resp.status_code}: {resp.text[:120]}")
    store["id"] = resp.json()["id"]
    return resp


def _bob_member(alice, bob, logs, course_id, bob_id):
    bob_id["id"] = _register_verify_login(bob, logs, "bob@example.com", "bob", 1)
    resp = alice.post(
        f"/courses/{course_id['id']}/members",
        json={"user_id": bob_id["id"]},
    )
    if resp.status_code != 201:
        raise AssertionError(f"{resp.status_code}: {resp.text[:120]}")
    return resp


def _note_create(client, course_id, store):
    resp = client.post(
        "/notes/",
        params={"generate_summary": "false"},
        json={"title": "N", "content": "content", "course_id": course_id["id"]},
    )
    if resp.status_code != 201:
        raise AssertionError(f"{resp.status_code}: {resp.text[:120]}")
    store["id"] = resp.json()["id"]
    return resp


def _video_upload(client, course_id, store):
    resp = client.post(
        "/videos/upload",
        data={
            "title": "V",
            "course_id": course_id["id"],
            "generate_transcript": "false",
        },
        files={"file": ("video.mp4", FAKE_MP4, "video/mp4")},
    )
    if resp.status_code != 201:
        raise AssertionError(f"{resp.status_code}: {resp.text[:120]}")
    store["id"] = resp.json()["id"]
    return resp


def _bad_magic(client, course_id):
    resp = client.post(
        "/videos/upload",
        data={"title": "V", "course_id": course_id["id"]},
        files={
            "file": ("fake.mp4", b"this-is-not-a-real-mp4-header-aaaa", "video/mp4")
        },
    )
    if resp.status_code != 400:
        raise AssertionError(f"status {resp.status_code} != 400 ({resp.text[:120]})")
    return resp


def _bob_private_course(alice, bob, store):
    resp = bob.post("/courses/", json={"title": "Bob Private"})
    if resp.status_code != 201:
        raise AssertionError(f"{resp.status_code}: {resp.text[:120]}")
    store["id"] = resp.json()["id"]
    resp = alice.get(f"/courses/{store['id']}")
    if resp.status_code != 404:
        raise AssertionError(
            f"alice saw bob's course: {resp.status_code} ({resp.text[:120]})"
        )
    return resp


if __name__ == "__main__":
    sys.exit(main())
