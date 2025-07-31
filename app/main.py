from fastapi import FastAPI
from dotenv import load_dotenv
import os

from app.routes import courses
from app.routes import quizzes
load_dotenv()

app = FastAPI()

app.include_router(courses.router)
app.include_router(quizzes.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))