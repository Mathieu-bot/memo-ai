from fastapi import FastAPI
from dotenv import load_dotenv
import os

from app.routes import ai, courses, notes, quizzes, videos

load_dotenv()

app = FastAPI()

app.include_router(ai.router)
app.include_router(courses.router)
app.include_router(notes.router)
app.include_router(quizzes.router)
app.include_router(videos.router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)