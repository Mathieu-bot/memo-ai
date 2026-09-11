import asyncio
import logging

from sqlalchemy.exc import SQLAlchemyError

import app.models  # noqa: F401  (registers all tables on Base.metadata)
from app.database import Base, engine

logger = logging.getLogger(__name__)


async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully.")
    except SQLAlchemyError as exc:
        logger.error("Database initialization failed: %s", exc)
        raise
    except Exception as exc:
        logger.error("Unexpected error during initialization: %s", exc)
        raise


if __name__ == "__main__":
    asyncio.run(init_db())
