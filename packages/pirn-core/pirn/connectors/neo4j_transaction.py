"""``Neo4jTransaction`` — Cypher statements inside an explicit Neo4j transaction.

Yielded by :meth:`Neo4jPool.transaction`, which has opened a session and begun an
explicit transaction on it. Unlike the pool's own methods — each of which opens a
session, runs one statement in an implicit transaction and closes the session
again — every statement here runs on the one open transaction, so the whole block
commits or rolls back together.

The bound "connection" is the ``neo4j.AsyncTransaction`` itself rather than a
connection: Neo4j's unit of work is the transaction object, and it is what
``run`` must be called on.

Algorithm:
    1. ``_check`` refuses a handle whose scope has ended. Cypher's bind markers
       are ``$name``, which the interpolation guard does not reject.
    2. ``run`` is called on the bound transaction; parameters are the Cypher
       parameter mapping, matching ``Neo4jPool``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_transaction import DatabaseTransaction


class Neo4jTransaction(DatabaseTransaction):
    """Run Cypher inside the explicit transaction a :class:`Neo4jPool` began."""

    async def execute(self, query: str, parameters: Iterable[Any] | None = None) -> None:
        """Run a Cypher statement, discarding its result."""
        self._check(query)
        await self._connection.run(query, dict(parameters) if parameters is not None else {})

    async def fetch_all(
        self, query: str, parameters: Iterable[Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a Cypher read and return its records as dicts."""
        self._check(query)
        result = await self._connection.run(
            query, dict(parameters) if parameters is not None else {}
        )
        records = await result.values()
        return [dict(r) for r in records]

    async def execute_many(self, query: str, parameter_seq: Iterable[Iterable[Any]]) -> None:
        """Run ``query`` once per parameter mapping, all in the one transaction."""
        for parameters in parameter_seq:
            await self.execute(query, parameters)
