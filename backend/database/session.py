from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from database.models import Base

# Load environment variables from .env file
load_dotenv()

# Get database URL and convert to async version if PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./espressobot.db")

# Convert PostgreSQL URL to use asyncpg driver and handle SSL
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    # Remove sslmode query parameter (not supported by asyncpg)
    if "?sslmode=" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.split("?sslmode=")[0]

# Configure SSL for remote connections
connect_args = {}
if "akamaidb.net" in DATABASE_URL or "supabase.co" in DATABASE_URL:
    connect_args = {"ssl": "require"}

# Connection-pool sizing for the background/awakening engine (separate from the
# API engine in database/models.py DatabaseManager). Explicitly sized + env-
# tunable: this pool backs awakenings/workflows/embedder, so it needs headroom
# for a busy fire-window (e.g. several users awakening at 09:20) without blocking.
# Kept modest because all pools share Supabase's max_connections=60 (direct
# conn) — see the 2026-06-30 pool-exhaustion incident. pool_recycle drops
# connections Supabase may have closed server-side. NOTE: only applied to
# Postgres — the sqlite dev/test fallback uses its own pool and rejects these.
_engine_kwargs = dict(
    echo=False,
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,
)
if DATABASE_URL.startswith("postgresql"):
    _engine_kwargs.update(
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
    )

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

def get_db_session():
    """Context manager for getting database session"""
    return AsyncSessionLocal()

from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db_context():
    """Async context manager for database session (for MCP servers)"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_async_session():
    """Async generator for database session (for scheduler and background tasks)"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)