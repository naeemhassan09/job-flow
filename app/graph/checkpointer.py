from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from app.config import get_settings


@asynccontextmanager
async def get_checkpointer() -> AsyncIterator[BaseCheckpointSaver]:
    """Yield a checkpointer appropriate for the current env.

    - test → MemorySaver (no Postgres needed)
    - local/dev/prod → AsyncPostgresSaver pinned to ``DATABASE_URL``

    The Postgres saver runs ``.setup()`` on first use to install its schema in
    a dedicated namespace; it does not touch the application tables.
    """
    settings = get_settings()
    if settings.app_env == "test":
        yield MemorySaver()
        return

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    conn_str = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    async with AsyncPostgresSaver.from_conn_string(conn_str) as saver:
        await saver.setup()
        yield saver
