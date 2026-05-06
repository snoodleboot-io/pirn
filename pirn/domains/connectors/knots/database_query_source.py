"""``DatabaseQuerySource`` — a pirn :class:`Source` that runs a parameterised
SELECT against any :class:`DatabaseConnectionPool` backend and returns rows.

Algorithm:
    1. Validate that ``pool`` is a :class:`DatabaseConnectionPool` and that
       ``query`` is a non-empty string.
    2. Look up ``pool.fetch_all``; raise ``TypeError`` if absent.
    3. Invoke ``await pool.fetch_all(query, parameters)`` and return rows as
       a list of tuples.


References:
    - :class:`pirn.domains.connectors.database_connection_pool.DatabaseConnectionPool`
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.knots.database_connection_pool_knot import DatabaseConnectionPoolKnot
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
        pool: DatabaseConnectionPoolKnot,
        query: Knot | str,
        parameters: Knot | tuple | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(pool=pool, query=query, parameters=parameters, _config=_config, **kwargs)

    async def process(
        self,
        pool: DatabaseConnectionPool,
        query: str,
        parameters: tuple[Any, ...] | None = None,
        **_: Any,
    ) -> list[tuple[Any, ...]]:
        """Run the configured SELECT query against the pool and return the result rows.

        Args:
            pool: The database connection pool to query against.
            query: The SQL SELECT query to execute.
            parameters: Optional tuple of bind parameters for the query.

        Returns:
            A list of row tuples returned by the database.

        Raises:
            TypeError: If pool is not a DatabaseConnectionPool or lacks fetch_all.
            ValueError: If query is empty.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                f"DatabaseQuerySource: pool must be a DatabaseConnectionPool, "
                f"got {type(pool).__name__}"
            )
        if not isinstance(query, str) or not query:
            raise ValueError("DatabaseQuerySource: query must be a non-empty string")
        # ``fetch_all`` is a method on every concrete pool we ship; it's not
        # part of the DatabaseConnectionPool interface so we duck-call it.
        # Concrete pools without fetch_all should subclass and add it.
        fetch_all = getattr(pool, "fetch_all", None)
        if fetch_all is None:
            raise TypeError(
                f"{type(pool).__name__} does not support fetch_all(); "
                "DatabaseQuerySource requires a pool with a fetch_all method"
            )
        params = parameters if parameters is not None else ()
        rows = await fetch_all(query, params)
        return list(rows)
