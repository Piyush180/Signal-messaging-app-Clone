"""
Database engine + session management (async SQLAlchemy 2.0).

Key ideas for beginners:
  - An "engine" is the pool of connections to the database.
  - A "session" is one unit of work (a set of reads/writes that commit together).
  - We hand out one session per HTTP request via the `get_db` dependency, and
    always close it afterwards. This prevents connection leaks.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# SQLite needs `check_same_thread=False` because the async driver touches the
# connection from different tasks. Other databases don't need this arg.
_engine_kwargs = {"echo": False, "future": True}
if settings.is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

# expire_on_commit=False => ORM objects stay usable after commit(), which we
# rely on when we serialize an object right after saving it.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class every ORM model inherits from."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a session and guarantees it is closed."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
