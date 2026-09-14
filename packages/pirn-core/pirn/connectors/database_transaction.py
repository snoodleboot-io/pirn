"""``DatabaseTransaction`` — the pool a :meth:`DatabaseConnectionPool.transaction` scope yields.

A transaction has to run every statement on one connection, but code that
issues statements is written against :class:`DatabaseConnectionPool`. This base
class bridges the two: it *is* a pool, bound to the single connection its owning
pool opened the transaction on, so ``async with pool.transaction() as tx:`` hands
the body something every pool-shaped helper already accepts.

Each concrete pool pairs with a subclass that implements ``fetch_all`` /
``execute`` / ``execute_many`` on the bound connection. Those statements issue no
transaction control of their own: the scope that yielded the handle commits or
rolls back.

Algorithm:
    1. The owning pool opens the transaction on a connection and constructs the
       handle with that connection and itself.
    2. Every statement method on the handle first calls :meth:`_check`, which
       refuses a handle whose scope has ended and applies the owning pool's
       inline-interpolation guard to the query.
    3. When the scope ends (commit or rollback), the owning pool calls
       :meth:`finish`; any later statement raises ``ConnectorClosedError``.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool


class DatabaseTransaction(DatabaseConnectionPool):
    """A pool bound to one connection inside one open transaction.

    Args:
        connection: The driver connection the transaction is open on.
        owner: The pool that opened the transaction; its interpolation guard
            applies to every statement run through the handle.
    """

    def __init__(self, connection: Any, owner: DatabaseConnectionPool) -> None:
        self._connection = connection
        self._owner = owner
        self._finished = False

    async def acquire(self) -> Any:
        """Return the bound connection; the scope, not the caller, releases it."""
        self._ensure_open()
        return self._connection

    async def release(self, connection: Any) -> None:
        """No-op: the transaction scope returns the connection when it ends."""
        return None

    async def close(self) -> None:
        """Refuse: the ``async with`` scope owns the connection and ends the transaction."""
        raise RuntimeError(
            f"{type(self).__name__}: a transaction is ended by leaving its "
            "`async with pool.transaction()` block, not by close()"
        )

    def transaction(self) -> AbstractAsyncContextManager[DatabaseConnectionPool]:
        """Refuse a nested transaction: statements on this handle already share one."""
        raise RuntimeError(
            f"{type(self).__name__}: already inside a transaction; issue the "
            "statements on this handle instead of opening a nested one"
        )

    def finish(self) -> None:
        """Mark the scope ended; called by the owning pool after commit or rollback."""
        self._finished = True

    def reject_inline_interpolation(self, query: str) -> None:
        """Apply the owning pool's placeholder grammar to ``query``."""
        self._owner.reject_inline_interpolation(query)

    def _check(self, query: str) -> None:
        """Refuse a finished handle, then guard ``query`` against inline interpolation."""
        self._ensure_open()
        self.reject_inline_interpolation(query)

    def _ensure_open(self) -> None:
        if self._finished:
            raise self._closed_error(type(self).__name__)
