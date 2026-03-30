"""Async session factory and FastAPI dependency."""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./omdt.db",
)

# SQLite needs connect_args for check_same_thread
_connect_args: dict[str, bool] = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine = create_async_engine(DATABASE_URL, echo=False, connect_args=_connect_args)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session (FastAPI dependency)."""
    async with async_session_factory() as session:
        yield session
