from fastapi import FastAPI
from dotenv import load_dotenv
import os

from app.routes import courses
from app.routes import quizzes
load_dotenv()

app = FastAPI()

app.include_router(courses.router)
app.include_router(quizzes.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the MemoAI API!"}