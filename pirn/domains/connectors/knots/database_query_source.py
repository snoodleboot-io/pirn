"""``DatabaseQuerySource`` — a pirn :class:`Source` that runs a parameterised
SELECT against any :class:`DatabaseConnectionPool` backend and returns rows.
"""

from __future__ import annotations

from typing import Any, Iterable

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.nodes.source import Source


class DatabaseQuerySource(Source):
    """Source that runs ``query`` (with optional ``parameters``) and returns
    the result rows as a list of tuples.

    The pool's safety check (``_reject_inline_interpolation``) still applies
    — passing a query with ``{...}`` or ``%s`` markers raises before any
    SQL hits the database.
    """

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        query: str,
        parameters: Iterable[Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                f"DatabaseQuerySource: pool must be a DatabaseConnectionPool, "
                f"got {type(pool).__name__}"
            )
        if not isinstance(query, str) or not query:
            raise ValueError("DatabaseQuerySource: query must be a non-empty string")
        self._pool = pool
        self._query = query
        self._parameters = tuple(parameters) if parameters is not None else ()
        super().__init__(_config=_config, **kwargs)

    @property
    def pool(self) -> DatabaseConnectionPool:
        return self._pool

    @property
    def query(self) -> str:
        return self._query

    @property
    def parameters(self) -> tuple[Any, ...]:
        return self._parameters

    async def process(self, **_: Any) -> list[tuple[Any, ...]]:
        """Run the configured SELECT query against the pool and return the result rows.

        Returns:
            A list of row tuples returned by the database.

        Raises:
            TypeError: If the pool does not support fetch_all.
        """
        # ``fetch_all`` is a method on every concrete pool we ship; it's not
        # part of the DatabaseConnectionPool interface so we duck-call it.
        # Concrete pools without fetch_all should subclass and add it.
        fetch_all = getattr(self._pool, "fetch_all", None)
        if fetch_all is None:
            raise TypeError(
                f"{type(self._pool).__name__} does not support fetch_all(); "
                "DatabaseQuerySource requires a pool with a fetch_all method"
            )
        rows = await fetch_all(self._query, self._parameters)
        return list(rows)
