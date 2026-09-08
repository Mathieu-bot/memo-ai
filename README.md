# MemoAI - Memorization Assistant for Students

[![CI](https://github.com/jiu/memo-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/jiu/memo-ai/actions/workflows/ci.yml)

MemoAI helps students memorize their lessons using AI to generate summaries, quizzes, and flashcards from their course notes and videos.

## Features

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

4. Get free API keys
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

- **Backend**: FastAPI, SQLAlchemy 2.0
- **Database**: SQLite by default (easily switchable to PostgreSQL via `DATABASE_URL`)
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
│   ├── database.py           # Engine, session, base
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