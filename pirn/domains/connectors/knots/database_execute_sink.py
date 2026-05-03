"""``DatabaseExecuteSink`` — a pirn :class:`Sink` that runs a parameterised
``INSERT`` / ``UPDATE`` / ``DELETE`` against any
:class:`DatabaseConnectionPool` backend, taking its row sequence from a
parent knot.
"""

from __future__ import annotations

from typing import Any, Iterable

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.nodes.sink import Sink


class DatabaseExecuteSink(Sink):
    """Sink that runs ``query`` once per parameter row from its parent.

    The parent knot must produce an iterable of parameter tuples — one
    invocation per tuple. Passing a single row instead of a list is a
    common mistake; this sink raises ``TypeError`` in that case.
    """

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        query: str,
        rows: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                f"DatabaseExecuteSink: pool must be a DatabaseConnectionPool, "
                f"got {type(pool).__name__}"
            )
        if not isinstance(query, str) or not query:
            raise ValueError("DatabaseExecuteSink: query must be a non-empty string")
        self._pool = pool
        self._query = query
        super().__init__(rows=rows, _config=_config, **kwargs)

    @property
    def pool(self) -> DatabaseConnectionPool:
        return self._pool

    @property
    def query(self) -> str:
        return self._query

    async def process(self, rows: Iterable[Iterable[Any]], **_: Any) -> int:
        """Execute the configured query once per parameter row and return the number of rows processed.

        Args:
            rows: An iterable of parameter tuples, one per query execution.

        Returns:
            The total number of parameter rows passed to execute_many.

        Raises:
            TypeError: If rows is a str/bytes value rather than an iterable of tuples, or if the pool lacks execute_many.
        """
        if isinstance(rows, (str, bytes, bytearray)):
            raise TypeError(
                "DatabaseExecuteSink: rows must be an iterable of parameter "
                "tuples, not a single str/bytes value"
            )
        materialised = [tuple(r) for r in rows]
        execute_many = getattr(self._pool, "execute_many", None)
        if execute_many is None:
            raise TypeError(
                f"{type(self._pool).__name__} does not support execute_many(); "
                "DatabaseExecuteSink requires a pool with an execute_many method"
            )
        await execute_many(self._query, materialised)
        return len(materialised)
