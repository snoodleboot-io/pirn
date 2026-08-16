"""``_SQLExecutor`` — internal helper Knot for :class:`SQLAgent`.

Validates an LLM-written SQL statement through two independent guards and
executes it. Internal API.

The two guards defend different threats and are both needed:

* :class:`~pirn_agents.tools.sql._read_only_sql_guard.ReadOnlySqlGuard` limits
  what the statement may *do* — it rejects anything that is not a single
  ``SELECT``/``WITH``. This is the guard the path was missing (PIR-817): the
  statement here is written by a model, so ``DROP TABLE``, ``UPDATE`` and DDL
  reached the database with nothing standing in the way.
* The pool's ``_reject_inline_interpolation`` limits how the statement's values
  got there — it rejects ``str.format``-style ``{...}`` and printf-style
  ``%s``/``%d`` markers, defending against prompt-injected dynamic SQL and
  accidental bad templating. It is an *injection* guard and says nothing about
  what the statement does, which is why it never substituted for the first.

Algorithm:
    1. Receive the ``sql`` query string and ``pool`` connection pool.
    2. Raise :class:`ValueError` if ``sql`` is empty.
    3. Run ``pool._reject_inline_interpolation(sql)`` — always, in both modes.
    4. In read-only mode (the default), run
       :meth:`ReadOnlySqlGuard.assert_read_only`, then read via ``fetch_all``
       when the pool offers it.
    5. When writes are opted in, execute on an acquired connection and commit
       or roll back exactly the transaction this statement opened.
    6. Return the rows as a plain list.

Math:
    No numeric computation.

References:
    - OWASP SQL injection prevention:
      https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.tools.sql._read_only_sql_guard import ReadOnlySqlGuard


class _SQLExecutor(Knot):
    """Validate the SQL through both guards and run it, read-only by default."""

    # Shared, stateless guard — built once per class, mirroring the ClassVar
    # prompt bindings on ``_SQLGenerator``.
    _guard: ClassVar[ReadOnlySqlGuard] = ReadOnlySqlGuard()

    # Class-level fail-safe default, overridden per instance in ``__init__``
    # (the pattern ``Knot._frozen`` itself uses). An instance that somehow
    # reached ``process`` without running ``__init__`` stays read-only rather
    # than silently becoming writable.
    _read_only: bool = True

    def __init__(
        self,
        *,
        sql: Knot | str,
        pool: Knot | DatabaseConnectionPool,
        _config: KnotConfig,
        read_only: bool = True,
        **kwargs: Any,
    ) -> None:
        """Bind the statement source, the pool, and the write policy.

        Args:
            sql: The SQL statement, or the knot producing it.
            pool: The database connection pool, or the knot producing it.
            _config: Framework knot configuration.
            read_only: When ``True`` (the default), reject any statement that is
                not a single ``SELECT``/``WITH``. A :class:`SQLAgent` that
                writes is the exceptional case, so it must be opted into
                explicitly rather than being the default for model-generated
                SQL.

        Note:
            ``read_only`` is deliberately *not* forwarded to ``super().__init__``
            as a knot input. Knot inputs are graph edges, so a policy passed that
            way could be driven by another knot's output — including, on this
            pipeline, one derived from model text. Holding it as plain
            constructor state keeps the decision the operator's, fixed at
            construction, exactly as ``SqlServiceConnector`` and ``SqlQueryTool``
            hold theirs.
        """
        self._read_only = read_only
        super().__init__(sql=sql, pool=pool, _config=_config, **kwargs)

    async def process(self, sql: str, pool: DatabaseConnectionPool, **_: Any) -> list[Any]:
        """Validate the SQL against both guards and execute it, returning the rows.

        Args:
            sql: The non-empty SQL query string to validate and execute.
            pool: The database connection pool used to execute the query.

        Returns:
            A list of row values returned by the database.

        Raises:
            ValueError: If ``sql`` is empty, carries an inline-interpolation
                marker, or — in read-only mode — is not a single read.
        """
        if not isinstance(sql, str) or not sql:
            raise ValueError("SQLAgent: generator returned empty SQL")
        # Defends against prompt-injected dynamic SQL and accidental
        # ``str.format`` interpolation in the generated query. Runs in both
        # modes: opting in to writes opts out of the read-only guard only.
        pool._reject_inline_interpolation(sql)
        if self._read_only:
            self._guard.assert_read_only(sql)
            return await self._read(sql, pool)
        return await self._execute_owning_transaction(sql, pool)

    @staticmethod
    async def _read(sql: str, pool: DatabaseConnectionPool) -> list[Any]:
        """Run a guard-approved read and return its rows.

        The read-only guard has already proved this is a single ``SELECT``/
        ``WITH``, and ``sqlite3`` opens an implicit transaction for DML only, so
        no transaction can be outstanding and there is nothing to commit. That
        matters beyond tidiness: under ``journal_mode=DELETE`` a ``COMMIT`` must
        take the exclusive lock, so committing here would make a query that only
        read rows fail with ``database is locked`` against a concurrent reader.
        """
        if hasattr(pool, "fetch_all"):
            rows = await pool.fetch_all(sql)  # type: ignore[attr-defined]
            return list(rows)
        connection = await pool.acquire()
        try:
            cursor = await connection.execute(sql)
            try:
                rows = await cursor.fetchall()
            finally:
                await cursor.close()
        finally:
            await pool.release(connection)
        return list(rows)

    @classmethod
    async def _execute_owning_transaction(cls, sql: str, pool: DatabaseConnectionPool) -> list[Any]:
        """Run a statement that may write, committing exactly what it opened.

        **Transaction ownership.** This commits — or rolls back — exactly the
        transaction *its own statement* opened, and never touches one it found
        already open: the same guarantee
        :meth:`~pirn_agents.connectors.column_aware_sqlite_pool.ColumnAwareSqlitePool.fetch_columns`
        (PIR-801) and
        :meth:`~pirn_agents.tools.sql.aiosqlite_connector.AiosqliteConnector.execute`
        (PIR-807) make, so all four SQL paths in the package now carry one
        recognisable contract. ``sqlite3`` starts an implicit transaction for DML
        only, so comparing ``in_transaction`` before and after the statement
        identifies the owner precisely:

        * a write that succeeds is committed, so it is durable once this returns.
          Without that, a write opted into here was routed to core's
          ``SqlitePool.fetch_all`` — which, unlike its ``execute``, issues no
          ``COMMIT`` — and was discarded when the connection closed, silently and
          with no error (PIR-817);
        * a statement that raises is rolled back. ``UPDATE ... OR FAIL`` aborts
          mid-statement while *keeping* the rows it already changed and leaves the
          transaction open, so without the rollback that partial write survives to
          be committed by whatever runs next — including a pure read;
        * a read, and DDL, open no transaction and so neither commit nor roll back.

        A caller driving the pool directly can therefore hold a multi-statement
        transaction across these calls and remains the only one who may end it.
        """
        connection = await pool.acquire()
        in_transaction_on_entry = bool(connection.in_transaction)
        try:
            try:
                cursor = await connection.execute(sql)
                try:
                    rows = await cursor.fetchall()
                finally:
                    await cursor.close()
            except BaseException:
                if cls._opened_transaction(connection, in_transaction_on_entry):
                    await connection.rollback()
                raise
            if cls._opened_transaction(connection, in_transaction_on_entry):
                await connection.commit()
        finally:
            await pool.release(connection)
        return list(rows)

    @staticmethod
    def _opened_transaction(connection: Any, in_transaction_on_entry: bool) -> bool:
        """Whether the statement just run is what opened the now-open transaction.

        Args:
            connection: The connection the statement ran on.
            in_transaction_on_entry: ``connection.in_transaction`` sampled before
                the statement ran.

        Returns:
            ``True`` only when a transaction is open now and none was open before,
            which makes this call its owner — and so the one responsible for
            ending it.
        """
        return bool(connection.in_transaction) and not in_transaction_on_entry
