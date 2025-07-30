from app.services.db import engine, Base
# Import all models to ensure they are registered with SQLAlchemy
from app.models.course import Course
from app.models.quiz import Quiz
from app.models.question import Question
from app.models.answer import Answer
from app.models.note import Note
from app.models.video import Video

Base.metadata.create_all(bind=engine)