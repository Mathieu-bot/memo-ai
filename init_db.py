from app.services.db import engine, Base
from app.models.course import Course
from app.models.quiz import Quiz
from app.models.question import Question
from app.models.answer import Answer
from app.models.note import Note
from app.models.video import Video

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

def init_db():
    try:
        Base.registry.configure()
        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully.")

        with Session(engine) as session:
            if session.query(Course).count() == 0:
                course = Course(title="Introduction to Python", description="Learn Python basics")
                session.add(course)
                session.commit()
                print("Initial data (course) seeded successfully.")
            else:
                print("Database already contains data, skipping seeding.")

    except SQLAlchemyError as e:
        print(f"Database initialization failed: {str(e)}")
        raise
    except Exception as e:
        print(f"Unexpected error during initialization: {str(e)}")
        raise

if __name__ == "__main__":
    init_db()