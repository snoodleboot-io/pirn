"""``DatabaseConnectionPoolKnot`` — vending Knot for a :class:`DatabaseConnectionPool`.

Wraps an externally-constructed pool so it participates in the pirn graph
with full lineage. Consumers receive the resolved pool value in their
``process()`` calls.

Algorithm:
    1. Accept the pool value (resolved by the framework from an upstream
       Knot or a scalar passed at pipeline-build time).
    2. Return it unchanged so downstream Knots receive the pool instance.


References:
    - :class:`pirn.connectors.database_connection_pool.DatabaseConnectionPool`
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class DatabaseConnectionPoolKnot(Knot):
    def __init__(
        self, *, pool: Knot | DatabaseConnectionPool, _config: KnotConfig, **kwargs: Any
    ) -> None:
        super().__init__(pool=pool, _config=_config, **kwargs)

    async def process(self, pool: DatabaseConnectionPool, **_: Any) -> DatabaseConnectionPool:
        return pool
