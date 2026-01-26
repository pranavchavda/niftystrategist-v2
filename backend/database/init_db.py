"""
Database initialization script
"""
import os
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from .models import Base

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/espressobot')

async def init_database():
    """Initialize the database tables"""
    # Convert to async URL if needed
    if DATABASE_URL.startswith("postgresql://"):
        async_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    else:
        async_url = DATABASE_URL

    logger.info(f"Initializing database at {async_url}")

    # Create engine
    engine = create_async_engine(async_url, echo=True)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully")

    # Close the engine
    await engine.dispose()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(init_database())