"""Connection pool wrapper around the synchronous :mod:`oracledb` driver.

The Oracle Python driver (``python-oracledb``) is synchronous; calls run
in a worker thread via :func:`asyncio.to_thread` so the connector
cooperates with pirn's async runtime without blocking the event loop on
long queries.

Parameter style: Oracle uses ``:name`` named binds. Both ``{...}`` brace
interpolation and ``%s``-style markers are rejected — pass parameters
through the driver's bind mechanism instead.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.oracle_config import OracleConfig
from pirn.connectors.dsn_scrubber import DsnScrubber


class OraclePool(DatabaseConnectionPool):
    """Single-client Oracle pool driven through ``asyncio.to_thread``.

    The injected ``client`` is treated as opaque: ``acquire`` returns it,
    ``release`` is a no-op. Cursors are opened per call and closed eagerly.

    It must be a *connection*, not a session pool: every statement method calls
    ``client.cursor()``, which ``oracledb.ConnectionPool`` does not provide —
    it exposes ``acquire``/``release`` instead. Both construction seams now
    honour that. The ``config=`` path builds its client with
    ``oracledb.connect`` (PIR-824); it previously used ``oracledb.create_pool``
    and so produced an object every statement failed on, undetected because
    nothing ever exercised it.

    **This class holds one connection for its lifetime** — that is the meaning
    of ``acquire`` returning the shared client and ``release`` being a no-op,
    and it is load bearing for the transaction ownership described below, which
    compares session state before and after a statement on the *same* session.
    Checking a connection out per call, as
    :class:`~pirn.connectors.databases.mssql_pool.MssqlPool` does, would be a
    different class with a different mechanism, not a drop-in change.

    **Transaction ownership.** Every statement method here commits — or rolls
    back — exactly the transaction *its own statement* opened, and never touches
    one it found already open. This is the guarantee
    :class:`~pirn.connectors.databases.sqlite_pool.SqlitePool` (PIR-819),
    ``ColumnAwareSqlitePool`` (PIR-801), ``AiosqliteConnector`` /
    ``SqliteConnector`` (PIR-807) and ``_SQLExecutor`` (PIR-817) already make.

    python-oracledb does **not** autocommit, and this pool holds one long-lived
    connection that ``acquire`` hands to every caller, so without this the
    ``INSERT`` a caller ran stayed in an open transaction that ``close``
    discarded — the write was lost silently and with no error (PIR-821).

    The discriminator is ``Connection.transaction_in_progress``, the driver's
    own report of whether a transaction is open on the session; it is the
    Oracle analogue of ``sqlite3.Connection.in_transaction``. Sampling it before
    and after the statement identifies the owner precisely:

    * a write that succeeds is committed, so it is durable once the call
      returns;
    * a statement that raises is rolled back. ``executemany`` without
      ``batcherrors`` stops at the first failing row while *keeping* the rows it
      already applied and leaves the transaction open, so without the rollback
      that partial batch survived to be committed by whatever ran next;
    * a read opens no transaction and so issues no ``COMMIT``. That is load
      bearing rather than tidiness — a ``COMMIT`` can take locks and make a
      query that only read rows fail — and it also keeps a concurrent reader on
      this shared connection from ending a writer's transaction under them.

    A caller driving this pool directly can therefore hold a multi-statement
    transaction across these calls and remains the only one who may end it.

    ``transaction_in_progress`` arrived in python-oracledb 2.3, and the
    ``client=`` seam accepts any connection-shaped object, so it may be absent.
    When it cannot be read, the state is unknown rather than "no transaction",
    and the two paths resolve that differently: the write paths commit — losing
    a write is worse than adopting a transaction, and it matches what
    :class:`~pirn.connectors.databases.mssql_pool.MssqlPool` and
    :class:`~pirn.connectors.databases.mysql_pool.MysqlPool` do unconditionally
    — while the read path still commits nothing.
    """

    def __init__(
        self,
        config: OracleConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("OraclePool requires either config= or client=")
        if config is not None and not isinstance(config, OracleConfig):
            raise TypeError(
                f"OraclePool: config must be an OracleConfig instance, got {type(config).__name__}"
            )
        self._config = config
        self._client = client
        self._closed = False
        # Oracle uses ``:name`` named binds. Reject brace interpolation
        # AND ``%s``-style markers (which would mask a port from another
        # dialect's client).
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> OracleConfig | None:
        return self._config

    async def acquire(self) -> Any:
        return await self._ensure_client()

    async def release(self, connection: Any) -> None:
        return None

    async def close(self) -> None:
        if self._client is not None:
            close_fn = getattr(self._client, "close", None)
            if callable(close_fn):
                await asyncio.to_thread(close_fn)
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("oracle.close")

    async def execute(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> Any:
        """Run a parameterised statement and return its row count.

        Commits only the transaction this statement opened — see the class
        docstring for why that is not an unconditional commit.
        """
        self._reject_inline_interpolation(query)
        client = await self._ensure_client()
        params = list(parameters or ())

        def _run() -> Any:
            in_transaction_on_entry = self._transaction_in_progress(client)
            try:
                cursor = client.cursor()
                try:
                    cursor.execute(query, params)
                    rowcount = cursor.rowcount
                finally:
                    cursor.close()
            except BaseException:
                if self._opened_transaction(
                    client, in_transaction_on_entry, when_unreportable=True
                ):
                    self._rollback(client)
                raise
            if self._opened_transaction(client, in_transaction_on_entry, when_unreportable=True):
                self._commit(client)
            return rowcount

        return await asyncio.to_thread(_run)

    async def fetch_all(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> list[tuple[Any, ...]]:
        """Run a parameterised SELECT and return all rows as tuples.

        A read opens no transaction and so issues no ``COMMIT``. A DML statement
        reaching here is rolled back rather than left stranded on the shared
        connection — see the class docstring.
        """
        self._reject_inline_interpolation(query)
        client = await self._ensure_client()
        params = list(parameters or ())

        def _run() -> list[tuple[Any, ...]]:
            in_transaction_on_entry = self._transaction_in_progress(client)
            try:
                cursor = client.cursor()
                try:
                    cursor.execute(query, params)
                    rows = [tuple(r) for r in cursor.fetchall()]
                finally:
                    cursor.close()
            except BaseException:
                if self._opened_transaction(
                    client, in_transaction_on_entry, when_unreportable=False
                ):
                    self._rollback(client)
                raise
            if self._opened_transaction(client, in_transaction_on_entry, when_unreportable=False):
                self._commit(client)
            return rows

        return await asyncio.to_thread(_run)

    async def execute_many(
        self,
        query: str,
        parameter_seq: Iterable[Iterable[Any]],
    ) -> Any:
        """Run a parameterised statement against a sequence of parameter tuples.

        Commits only the transaction this statement opened — see the class
        docstring for why that is not an unconditional commit.
        """
        self._reject_inline_interpolation(query)
        client = await self._ensure_client()
        rows = [list(p) for p in parameter_seq]

        def _run() -> Any:
            in_transaction_on_entry = self._transaction_in_progress(client)
            try:
                cursor = client.cursor()
                try:
                    cursor.executemany(query, rows)
                    rowcount = cursor.rowcount
                finally:
                    cursor.close()
            except BaseException:
                if self._opened_transaction(
                    client, in_transaction_on_entry, when_unreportable=True
                ):
                    self._rollback(client)
                raise
            if self._opened_transaction(client, in_transaction_on_entry, when_unreportable=True):
                self._commit(client)
            return rowcount

        return await asyncio.to_thread(_run)

    @staticmethod
    def _transaction_in_progress(client: Any) -> bool | None:
        """Whether a transaction is open on ``client``, or ``None`` if unknown.

        Reading the flag is a driver call, not a local attribute: python-oracledb
        verifies the session is still connected and raises if it is not. Since
        this is sampled on the failure path too, a raise here would replace the
        statement's own error with a confusing one — so a client that cannot
        answer is reported as unknown rather than allowed to propagate.

        Args:
            client: The ``oracledb``-shaped connection the statement runs on.

        Returns:
            The driver's ``transaction_in_progress`` flag, or ``None`` when the
            client does not report one — python-oracledb gained the attribute in
            2.3, and the ``client=`` seam accepts any connection-shaped object.
        """
        try:
            flag = getattr(client, "transaction_in_progress", None)
        except Exception:
            # Any driver error reading the flag means the same thing here: the
            # client cannot answer, so ownership is undecidable.
            return None
        return bool(flag) if isinstance(flag, bool) else None

    @classmethod
    def _opened_transaction(
        cls,
        client: Any,
        in_transaction_on_entry: bool | None,
        *,
        when_unreportable: bool,
    ) -> bool:
        """Whether the statement just run is what opened the now-open transaction.

        Args:
            client: The ``oracledb``-shaped connection the statement ran on.
            in_transaction_on_entry: ``transaction_in_progress`` sampled before
                the statement ran, or ``None`` if the client does not report it.
            when_unreportable: What to conclude when the flag cannot be read at
                either sampling point, and ownership is therefore undecidable.
                The write paths pass ``True`` so an unreportable client still
                gets a durable write; the read path passes ``False`` so a read
                never commits.

        Returns:
            ``True`` only when a transaction is open now and none was open
            before, which makes this call its owner — and so the one responsible
            for ending it.
        """
        in_transaction_now = cls._transaction_in_progress(client)
        if in_transaction_on_entry is None or in_transaction_now is None:
            return when_unreportable
        return in_transaction_now and not in_transaction_on_entry

    @staticmethod
    def _commit(client: Any) -> None:
        """Commit on ``client`` if it offers a commit at all."""
        commit_fn = getattr(client, "commit", None)
        if callable(commit_fn):
            commit_fn()

    @staticmethod
    def _rollback(client: Any) -> None:
        """Roll back on ``client`` if it offers a rollback at all."""
        rollback_fn = getattr(client, "rollback", None)
        if callable(rollback_fn):
            rollback_fn()

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("OraclePool is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import oracledb  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "OraclePool requires oracledb; install via `pip install pirn[oracle]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("OraclePool: missing config and no injected client")

        # `connect`, not `create_pool` (PIR-824). This path used to build an
        # `oracledb.ConnectionPool`, which exposes acquire/release/close/drop
        # and **no** `cursor()` — so every statement method here failed on it
        # with AttributeError the moment it ran. It never did run: nothing in
        # the tree constructed `OraclePool(config=...)` and executed anything,
        # which is how a broken public path stayed broken.
        #
        # A single connection is the shape this class already has — `acquire`
        # returns the one client and `release` is a no-op — and it is what the
        # transaction-ownership sampling added by PIR-821 depends on, since
        # that compares `transaction_in_progress` before and after a statement
        # on the *same* session. Handing each call a different pooled
        # connection would quietly invalidate it.
        kwargs: dict[str, Any] = {}
        for name, key in (
            ("user", "user"),
            ("password", "password"),
            ("dsn", "dsn"),
            ("wallet_location", "wallet_location"),
        ):
            value = getattr(self._config, name)
            if value is not None:
                kwargs[key] = value
        try:
            client = await asyncio.to_thread(oracledb.connect, **kwargs)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("oracle.connect")
        return client
