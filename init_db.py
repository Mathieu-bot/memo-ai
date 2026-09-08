import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.models import Course

logger = logging.getLogger(__name__)


def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")

        with Session(engine) as session:
            if session.query(Course).count() == 0:
                course = Course(
                    title="Introduction to Python",
                    description="Learn Python basics",
                )
                session.add(course)
                session.commit()
                logger.info("Initial data (course) seeded successfully.")
            else:
                logger.info("Database already contains data, skipping seeding.")

    except SQLAlchemyError as exc:
        logger.error("Database initialization failed: %s", exc)
        raise
    except Exception as exc:
        logger.error("Unexpected error during initialization: %s", exc)
        raise


if __name__ == "__main__":
    init_db()
