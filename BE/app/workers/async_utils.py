import asyncio
from collections.abc import Coroutine
from typing import TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine[None, None, T]) -> T:
    """Huey tasks are plain sync functions; our sync/DB code is async (SQLAlchemy asyncio,
    httpx.AsyncClient). Each task gets its own event loop rather than sharing one across the
    worker process, since Huey may run tasks in separate threads/greenlets."""
    return asyncio.run(coro)
