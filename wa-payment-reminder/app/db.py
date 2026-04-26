"""
Database module using asyncpg.
Provides connection pool management and query execution functions.
"""
import asyncio
import time
from typing import Any, Optional, List
import asyncpg
from app.config import settings

# Module-level pool instance
_pool: Optional[asyncpg.Pool] = None


async def init_pool() -> None:
    """Initialize the asyncpg connection pool."""
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        ssl="require",
        min_size=1,
        max_size=10,
        command_timeout=30,
    )
    print("Database pool initialized")


async def close_pool() -> None:
    """Close the connection pool gracefully."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        print("Database pool closed")


def get_pool() -> asyncpg.Pool:
    """Get the current pool instance."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    return _pool


async def execute(sql: str, *args: Any) -> str:
    """
    Execute a SQL query (INSERT, UPDATE, DELETE).
    Returns the command status.
    """
    pool = get_pool()
    start = time.time()
    async with pool.acquire() as conn:
        result = await conn.execute(sql, *args)
    elapsed = time.time() - start
    if elapsed > 0.2:
        print(f"SLOW QUERY ({elapsed:.3f}s): {sql[:100]}...")
    return result


async def fetch(sql: str, *args: Any) -> List[asyncpg.Record]:
    """
    Fetch multiple rows from a SELECT query.
    Returns a list of Records.
    """
    pool = get_pool()
    start = time.time()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)
    elapsed = time.time() - start
    if elapsed > 0.2:
        print(f"SLOW QUERY ({elapsed:.3f}s): {sql[:100]}...")
    return rows


async def fetchrow(sql: str, *args: Any) -> Optional[asyncpg.Record]:
    """
    Fetch a single row from a SELECT query.
    Returns a Record or None if no rows found.
    """
    pool = get_pool()
    start = time.time()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *args)
    elapsed = time.time() - start
    if elapsed > 0.2:
        print(f"SLOW QUERY ({elapsed:.3f}s): {sql[:100]}...")
    return row
