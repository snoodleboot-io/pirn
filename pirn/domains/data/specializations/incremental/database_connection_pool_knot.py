"""``DatabaseConnectionPoolKnot`` — vending Knot for :class:`DatabaseConnectionPool`.

A :class:`~pirn.domains.connectors.database_connection_pool.DatabaseConnectionPool`
is a live stateful object (connection handles, async state) that should not be
passed directly as a constructor argument to consumer Knots — doing so bypasses
graph registration and makes the dependency invisible to the tapestry. This
vending Knot puts the pool on the graph so consumer Knots can declare it as a
typed upstream dependency and receive the resolved pool in their own
``process()`` calls.

The pool itself is constructed outside the tapestry (e.g. from a
:class:`~pirn.domains.connectors.databases.sqlite_config.SqliteConfig` or a
:class:`~pirn.domains.connectors.databases.postgres_config.PostgresConfig`)
and passed in as a scalar ``Knot | DatabaseConnectionPool`` input, which the
framework auto-coerces into a :class:`~pirn.nodes.parameter.Parameter` node.

Algorithm:
    1. Receive the resolved :class:`DatabaseConnectionPool` in ``process()``.
    2. Return it unchanged so downstream Knots receive it as a typed value.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — PirnOpaqueValue (opaque pydantic schema for live resources):
        pirn/core/pirn_opaque_value.py
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool


class DatabaseConnectionPoolKnot(Knot):
    """Vend a :class:`DatabaseConnectionPool` through the pirn graph.

    Pass any concrete pool (``SqlitePool``, ``DuckdbPool``, ``PostgresPool``,
    etc.) as the ``pool`` argument. Consumer Knots declare this Knot as a
    typed ``__init__`` parameter and receive the resolved pool in their own
    ``process()`` calls.
    """

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(pool=pool, _config=_config, **kwargs)

    async def process(self, pool: DatabaseConnectionPool, **_: Any) -> DatabaseConnectionPool:
        """Return the resolved connection pool.

        Args:
            pool: The resolved :class:`DatabaseConnectionPool` instance.

        Returns:
            The same pool, passed through unchanged.
        """
        return pool
