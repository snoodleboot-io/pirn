from __future__ import annotations

import re
from typing import Any


def _sanitize_dsn(dsn: str) -> str:
    """Replace credentials in a DSN with <redacted> for safe logging/display."""
    return re.sub(r'(://)[^@]+(@)', r'\1<redacted>\2', dsn)


class _LazyPool:
    """Wraps either an injected pool (test / sharing) or a DSN string.

    When a DSN is given the asyncpg pool is created lazily on first use.
    """

    def __init__(self, pool: Any = None, dsn: str | None = None) -> None:
        if pool is None and dsn is None:
            raise TypeError("provide either pool= or dsn=")
        self._pool = pool
        self._dsn = dsn
        self._dsn_display = _sanitize_dsn(dsn) if dsn else None

    async def get(self) -> Any:
        if self._pool is None:
            try:
                import asyncpg
            except ImportError as exc:
                raise ImportError(
                    "PostgresStore/PostgresHistory require asyncpg; install "
                    "via `pip install pirn[postgres]`"
                ) from exc
            try:
                self._pool = await asyncpg.create_pool(self._dsn)
            except Exception as exc:
                safe_msg = _sanitize_dsn(str(exc))
                raise type(exc)(safe_msg) from None
        return self._pool

    async def close(self) -> None:
        if self._pool is not None and self._dsn is not None:
            await self._pool.close()
            self._pool = None
