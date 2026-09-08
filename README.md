# MemoAI - Memorization Assistant for Students

[![CI](https://github.com/jiu/memo-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/jiu/memo-ai/actions/workflows/ci.yml)

MemoAI helps students memorize their lessons using AI to generate summaries, quizzes, and flashcards from their course notes and videos.

## Features

- **User Authentication**: email-based accounts with unique usernames, JWT login
  and mandatory email verification
- **Course Management**: Organize your courses and their content
- **Course Notes**: Add your notes and get AI-generated summaries
- **Quiz Generation**: Create quizzes to test your knowledge
- **Flashcards**: Generate flashcards for active recall
- **Video Upload**: Store your course videos in the cloud (Cloudinary)
- **Video Transcription**: Get transcriptions of your videos

## AI Stack ($0 budget)

| Task | Provider | Model | Free Tier |
|------|----------|-------|-----------|
| Text generation (quizzes, summaries, flashcards) | Google Gemini | `gemini-2.5-flash` | 10 RPM, 1500 RPD |
| Audio transcription | Groq | `whisper-large-v3-turbo` | ~8 hours of audio/day |
| Video storage | Cloudinary | - | 25 GB, 25 credits/month |

## Installation

1. Clone this repository
   ```bash
   git clone https://github.com/your-username/memoai.git
   cd memoai
   ```

2. Create a virtual environment and install dependencies
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Copy the `.env.example` file to `.env` and configure your environment variables
   ```bash
   cp .env.example .env
   ```
   Then generate a strong `JWT_SECRET`:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

4. Install the `ffmpeg` system requirement (used to chunk large videos before
   transcription, see [Architecture Principles](#architecture-principles))
   ```bash
   # Debian/Ubuntu
   sudo apt install ffmpeg
   # macOS
   brew install ffmpeg
   # Windows (via winget)
   winget install ffmpeg
   ```

5. Get free API keys
   - **Gemini**: https://aistudio.google.com (generate `GEMINI_API_KEY`)
   - **Groq**: https://console.groq.com (generate `GROQ_API_KEY`)
   - **Cloudinary**: https://cloudinary.com (free account)

5. Initialize the database
   ```bash
   python init_db.py
   ```

6. Start the application
   ```bash
   uvicorn app.main:app --reload
   ```

7. Access the API at http://localhost:8000
   - Interactive docs: http://localhost:8000/docs

## Running with Docker

Requires [Docker](https://docs.docker.com/get-docker/) and Docker Compose.

```bash
# 1. Configure the environment (create your JWT_SECRET too)
cp .env.example .env

# 2. Build and start
docker-compose up --build
```

Notes:
- Database tables are created and seeded automatically on container start
  (`docker-entrypoint.sh` runs `init_db.py`, it is idempotent).
- The SQLite file lives in the `data/` folder (bind-mounted from `./data`).
  Delete it to reset the database.
- `DATABASE_URL` is overridden by `docker-compose.yml` to point to `/data/memoai.db`.
- The API listens on http://localhost:8000 (or `http://localhost:8000/docs`).

## Authentication

Accounts use **email as login identifier** + a **unique username**. Email
**verification is mandatory**: new users must verify their email before they can
use the API. In this MVP the verification link is printed to the server logs
(in production, hook it to a real email service via `on_after_request_verify`
in `app/auth.py`).

```bash
# 1. Register (returns the user; is_verified is False)
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"student@example.com","password":"password123","username":"alice"}'

# 2. Request a verification token
curl -X POST http://localhost:8000/auth/request-verify-token \
  -H "Content-Type: application/json" \
  -d '{"email":"student@example.com"}'

# 3. Verify with the token logged by the server
curl -X POST http://localhost:8000/auth/verify \
  -H "Content-Type: application/json" \
  -d '{"token":"<token-from-server-logs>"}'

# 4. Login (form data) -> access_token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'username=student@example.com&password=password123'

# 5. Use the token on any protected endpoint
curl http://localhost:8000/courses/ \
  -H "Authorization: Bearer <access_token>"
```

All endpoints except `/auth/*` and `/users/*` require a verified, authenticated
user.

## Development Workflow

- **Formatting & linting** are handled by [Ruff](https://docs.astral.sh/ruff/) (Python's
  equivalent of Prettier/ESLint). Install it once: `pip install -r requirements.txt`

```bash
ruff check .              # lint
ruff format .             # auto-format (like prettier --write)
ruff format --check .     # verify in CI
```

- **CI** runs automatically on every push/PR via GitHub Actions
  (`.github/workflows/ci.yml`): lint checks, format checks, and the full
  test suite on Python 3.11 & 3.12.

## Running Tests

```bash
pytest tests/ -v
```

## Technologies Used

- **Backend**: FastAPI, SQLAlchemy 2.0 (async), fastapi-users (auth), PyJWT
- **Database**: SQLite via aiosqlite by default (easily switchable to PostgreSQL via `DATABASE_URL`)
- **AI**: Google Gemini (text), Groq Whisper (transcription)
- **Video storage**: Cloudinary
- **Validation**: Pydantic v2
- **Linting & formatting**: Ruff

## Project Structure

```
memoai/
├── app/
│   ├── main.py               # App factory, middleware, router registration
│   ├── config.py             # Pydantic Settings (all configuration)
│   ├── auth.py               # fastapi-users wiring (JWT, verification)
│   ├── database.py           # Async engine, session, base
│   ├── dependencies.py       # Shared FastAPI dependencies
│   ├── exceptions.py         # Business exceptions + global handlers
│   ├── models/               # SQLAlchemy models (one file per entity)
│   ├── schemas/              # Pydantic v2 schemas (one file per domain)
│   ├── routers/              # Thin HTTP layer (one file per resource)
│   └── services/
│       ├── ai/               # Abstract AI provider + Gemini + domain services
│       │   ├── base.py           # AIProvider interface
│       │   ├── gemini.py         # Gemini implementation (retry/backoff)
│       │   ├── quiz_generator.py
│       │   ├── summary_service.py
│       │   ├── flashcard_service.py
│       │   └── transcription_service.py  # Groq Whisper + chunking
│       ├── cloudinary_service.py
│       └── video_service.py
├── tests/                    # pytest suite
├── .env.example
├── init_db.py
└── README.md
```

## Architecture Principles

- **Single Responsibility**: routers handle HTTP, services handle business logic,
  models handle persistence, schemas handle validation
- **Abstract AI provider**: swap Gemini for another provider by implementing the
  `AIProvider` interface
- **Graceful degradation**: if no AI key is configured, notes still save (summary
  stays null) and AI endpoints return clean `503` responses
- **Retry with exponential backoff**: transient AI rate limits are handled
  automatically (3 attempts max)
- **Automatic audio chunking**: videos larger than 25 MB are chunked with ffmpeg
  to stay within Groq's free tier upload limit

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Create an account (email, password, username) |
| POST | `/auth/login` | Login with email + password (form data) -> JWT |
| POST | `/auth/logout` | Invalidate the current token |
| POST | `/auth/request-verify-token` | Request an email verification token |
| POST | `/auth/verify` | Verify an email with a token |
| POST | `/auth/forgot-password` | Request a password reset token |
| POST | `/auth/reset-password` | Reset the password with a token |
| GET/PATCH | `/users/me` | Get / update the current user |
| GET/PATCH/DELETE | `/users/{id}` | Get / update / delete a user (authenticated) |
| GET/POST | `/courses/` | List / create courses |
| GET/PUT/DELETE | `/courses/{id}` | Get / update / delete a course |
| GET/POST | `/quizzes/` | List / create quizzes |
| GET/PUT/DELETE | `/quizzes/{id}` | Get / update / delete a quiz |
| GET/POST | `/notes/` | List / create notes |
| GET/PUT/DELETE | `/notes/{id}` | Get / update / delete a note |
| POST | `/notes/{id}/summarize` | Generate AI summary |
| POST | `/notes/{id}/generate-flashcards` | Generate AI flashcards |
| GET/POST | `/videos/` | List / upload videos (multipart) |
| GET/PUT/DELETE | `/videos/{id}` | Get / update / delete a video |
| POST | `/videos/{id}/regenerate-transcript` | Regenerate AI transcript |
| POST | `/ai/generate-quiz/{course_id}` | Generate AI quiz for a course |

## License

This project is licensed under the MIT License. See the LICENSE file for more information.