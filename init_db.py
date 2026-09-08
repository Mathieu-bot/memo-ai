import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.database import Base, SessionLocal, engine
from app.models import Course

logger = logging.getLogger(__name__)


async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully.")

        async with SessionLocal() as session:
            count = await session.execute(select(func.count()).select_from(Course))
            if count.scalar_one() == 0:
                course = Course(
                    title="Introduction to Python",
                    description="Learn Python basics",
                )
                session.add(course)
                await session.commit()
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
    asyncio.run(init_db())
