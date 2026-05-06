"""``DatabaseExecuteSink`` — a pirn :class:`Sink` that runs a parameterised
``INSERT`` / ``UPDATE`` / ``DELETE`` against any
:class:`DatabaseConnectionPool` backend, taking its row sequence from a
parent knot.

Algorithm:
    1. Validate that ``pool`` is a :class:`DatabaseConnectionPool` and that
       ``query`` is a non-empty string.
    2. Validate that ``rows`` is not a ``str`` or ``bytes`` scalar (a common
       caller mistake).
    3. Materialise ``rows`` into a list of parameter tuples.
    4. Look up ``pool.execute_many``; raise ``TypeError`` if absent.
    5. Invoke ``await pool.execute_many(query, materialised)``.
    6. Return the count of rows processed.


References:
    - :class:`pirn.domains.connectors.database_connection_pool.DatabaseConnectionPool`
"""

from __future__ import annotations

from typing import Any, Iterable

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.knots.database_connection_pool_knot import DatabaseConnectionPoolKnot
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
        pool: DatabaseConnectionPoolKnot,
        query: Knot | str,
        rows: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(pool=pool, query=query, rows=rows, _config=_config, **kwargs)

    async def process(self, pool: DatabaseConnectionPool, query: str, rows: Iterable[Iterable[Any]], **_: Any) -> int:
        """Execute the configured query once per parameter row and return the number of rows processed.

        Args:
            pool: The database connection pool to execute against.
            query: The SQL query to execute for each row.
            rows: An iterable of parameter tuples, one per query execution.

        Returns:
            The total number of parameter rows passed to execute_many.

        Raises:
            TypeError: If pool is not a DatabaseConnectionPool, rows is a str/bytes value,
                or the pool lacks execute_many.
            ValueError: If query is empty.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                f"DatabaseExecuteSink: pool must be a DatabaseConnectionPool, "
                f"got {type(pool).__name__}"
            )
        if not isinstance(query, str) or not query:
            raise ValueError("DatabaseExecuteSink: query must be a non-empty string")
        if isinstance(rows, (str, bytes, bytearray)):
            raise TypeError(
                "DatabaseExecuteSink: rows must be an iterable of parameter "
                "tuples, not a single str/bytes value"
            )
        materialised = [tuple(r) for r in rows]
        execute_many = getattr(pool, "execute_many", None)
        if execute_many is None:
            raise TypeError(
                f"{type(pool).__name__} does not support execute_many(); "
                "DatabaseExecuteSink requires a pool with an execute_many method"
            )
        await execute_many(query, materialised)
        return len(materialised)
