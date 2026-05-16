from __future__ import annotations

import re
from typing import Any


class _LazyPool:
    """Wraps either an injected pool (test / sharing) or a DSN string.

    When a DSN is given the asyncpg pool is created lazily on first use.
    """

    @staticmethod
    def __sanitize_dsn(dsn: str) -> str:
        return re.sub(r"(://)[^@]+(@)", r"\1<redacted>\2", dsn)

    def __init__(self, pool: Any = None, dsn: str | None = None) -> None:
        """Initialise the wrapper.

        Args:
            pool: An existing asyncpg connection pool.  If provided, it is
                returned immediately from :meth:`get` without creating a new
                one.
            dsn: PostgreSQL DSN used to create a pool lazily on first
                :meth:`get` call.  Mutually exclusive with ``pool``.

        Raises:
            TypeError: If neither ``pool`` nor ``dsn`` is provided.
        """
        if pool is None and dsn is None:
            raise TypeError("provide either pool= or dsn=")
        self._pool = pool
        self._dsn = dsn
        self._dsn_display = self.__sanitize_dsn(dsn) if dsn else None

    async def get(self) -> Any:
        """Return the connection pool, creating it lazily if needed.

        Credentials in any exception messages are redacted before re-raising.

        Returns:
            An asyncpg connection pool.

        Raises:
            ImportError: If asyncpg is not installed.
            Exception: Any pool-creation failure with DSN credentials
                redacted.
        """
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
                safe_msg = self.__sanitize_dsn(str(exc))
                raise type(exc)(safe_msg) from None
        return self._pool

    async def close(self) -> None:
        """Close the pool if it was created internally from a DSN.

        Injected pools (created externally and passed as ``pool=``) are not
        closed here; the caller owns their lifecycle.
        """
        if self._pool is not None and self._dsn is not None:
            await self._pool.close()
            self._pool = None
