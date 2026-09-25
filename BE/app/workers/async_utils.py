import asyncio
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

T = TypeVar("T")


def run_async(coro: Coroutine[None, None, T]) -> T:
    """Huey tasks are plain sync functions; our sync/DB code is async (SQLAlchemy asyncio,
    httpx.AsyncClient). Each task gets its own event loop rather than sharing one across the
    worker process, since Huey may run tasks in separate threads/greenlets."""
    return asyncio.run(coro)


@asynccontextmanager
async def worker_session() -> AsyncIterator[AsyncSession]:
    """A DB session for worker tasks. Uses a throwaway engine with no connection pool: the app's
    shared pooled engine binds connections to whichever event loop first used them, and every
    task here runs in a fresh loop, so reusing pooled connections fails with "another operation
    is in progress"."""
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            yield session
    finally:
        await engine.dispose()
