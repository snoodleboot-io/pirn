"""``MongodbTransaction`` — collection writes inside a MongoDB multi-document transaction.

Yielded by :meth:`MongoDBPool.transaction`, which has started a client session and
opened a transaction on it. Every operation here passes that session, which is
what makes MongoDB treat the writes as one atomic unit; an operation issued
without it is not part of the transaction.

The bound "connection" is a ``(database, session)`` pair: the operations need the
database handle to reach a collection and the session to join the transaction.

MongoDB serves multi-document transactions on replica sets and sharded clusters
only. On a standalone ``mongod`` the driver raises when the transaction starts —
that is the deployment's answer, not this pool's, and it is left to propagate
rather than being downgraded to a non-atomic scope.

Algorithm:
    1. ``_check`` refuses a handle whose scope has ended. ``query`` is a
       collection name, so the interpolation guard passes it through.
    2. The operation runs on ``database[collection]`` with ``session=`` bound.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_transaction import DatabaseTransaction


class MongodbTransaction(DatabaseTransaction):
    """Insert and read documents inside the transaction a :class:`MongoDBPool` began."""

    async def execute(self, query: str, parameters: Iterable[Any] | None = None) -> str:
        """Insert one document into the ``query`` collection; returns its id."""
        self._check(query)
        database, session = self._connection
        document: Any = parameters if parameters is not None else {}
        result = await database[query].insert_one(document, session=session)
        return str(result.inserted_id)

    async def fetch_all(self, query: str, parameters: Iterable[Any] | None = None) -> list[Any]:
        """Read every document in the ``query`` collection matching the filter."""
        self._check(query)
        database, session = self._connection
        filter_document: Any = parameters if parameters is not None else {}
        cursor = database[query].find(filter_document, session=session)
        rows = await cursor.to_list(length=None)
        return [{k: v for k, v in document.items() if k != "_id"} for document in rows]

    async def execute_many(self, query: str, parameter_seq: Iterable[Iterable[Any]]) -> None:
        """Bulk-insert documents into the ``query`` collection."""
        self._check(query)
        database, session = self._connection
        await database[query].insert_many(list(parameter_seq), session=session)
