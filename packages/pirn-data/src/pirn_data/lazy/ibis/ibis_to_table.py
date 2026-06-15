"""``IbisToTable`` — terminal sink that compiles the deferred expression
to SQL (or the backend's plan format), executes it server-side, and
optionally writes the result into a destination table.

This is the only Tier-3 knot that *materialises*. Everything upstream
runs in deferred form. The materialisation result is not propagated back
to the caller as rows by default — that would defeat the push-down — so
the sink returns a small
:class:`pirn_data.lazy.ibis.ibis_execution_receipt.IbisExecutionReceipt`
describing what was executed and where the result went.

Algorithm:
    1. Validate that ``connection`` is not ``None``.
    2. Validate that ``target_table``, when set, is a non-empty string.
    3. Compile the deferred expression to a SQL string via
       ``connection.compile(expression)``.
    4. If no ``target_table``: execute the expression with
       ``connection.execute(expression)`` and count resulting rows.
    5. If ``target_table`` is set: optionally drop the existing table when
       ``overwrite=True``, then call ``connection.create_table(target_table, expression)``
       to materialise the result server-side; count rows via
       ``connection.execute(expression.count())``.
    6. Return an :class:`IbisExecutionReceipt` describing the outcome.

    ```text
    sql = str(connection.compile(expression))
    if target_table:
        if overwrite and target_table in connection.list_tables():
            connection.drop_table(target_table)
        connection.create_table(target_table, expression)
        row_count = int(connection.execute(expression.count()))
    else:
        executed = connection.execute(expression)
        row_count = len(executed)
    return IbisExecutionReceipt(...)
    ```

References:
    [1] Ibis — Backend.execute / compile:
        https://ibis-project.org/reference/backends.html
    [2] Ibis — Backend.create_table:
        https://ibis-project.org/reference/backends.html#ibis.backends.BaseBackend.create_table
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sink import Sink

from pirn_data.lazy.ibis.ibis_connection import IbisConnection
from pirn_data.lazy.ibis.ibis_execution_receipt import IbisExecutionReceipt
from pirn_data.lazy.ibis.ibis_table import IbisTable


class IbisToTable(Sink):
    """Compile and execute the deferred expression on its backend."""

    def __init__(
        self,
        *,
        batch: Knot,
        connection: Any,
        target_table: Knot | str | None = None,
        overwrite: Knot | bool = False,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            batch=batch,
            connection=connection,
            target_table=target_table,
            overwrite=overwrite,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        batch: IbisTable,
        connection: Any,
        target_table: Any,
        overwrite: Any,
        **_: Any,
    ) -> IbisExecutionReceipt:
        """Compile the deferred Ibis expression to SQL, execute it, and return an execution receipt.

        Args:
            batch: The upstream IbisTable whose deferred expression will be compiled and executed.
            connection: The Ibis backend connection.
            target_table: Optional name of a destination table to create, or None.
            overwrite: If True and target_table exists, drop it before creating.

        Returns:
            An IbisExecutionReceipt describing the backend, target table,
            compiled SQL, and row count.
        """
        if connection is None:
            raise TypeError("IbisToTable: connection is required")
        if target_table is not None and not isinstance(target_table, str):
            raise TypeError("IbisToTable: target_table must be a string or None")
        if target_table is not None and not target_table:
            raise ValueError("IbisToTable: target_table must be non-empty when set")

        backend = connection.backend if isinstance(connection, IbisConnection) else connection
        compiled_sql = str(backend.compile(batch.expression))

        row_count: int | None = None
        if target_table is None:
            executed = backend.execute(batch.expression)
            row_count = self._row_count(executed)
        else:
            self._materialise_to_table(batch, backend, target_table, overwrite)
            count_expr = batch.expression.count()
            row_count = int(backend.execute(count_expr))

        return IbisExecutionReceipt(
            backend_name=batch.backend_name,
            target_table=target_table,
            compiled_sql=compiled_sql,
            row_count=row_count,
            executed_at=datetime.now(UTC),
        )

    @staticmethod
    def _materialise_to_table(
        batch: IbisTable,
        connection: Any,
        target_table: str,
        overwrite: Any,
    ) -> None:
        if overwrite and target_table in connection.list_tables():
            connection.drop_table(target_table)
        connection.create_table(target_table, batch.expression)

    @staticmethod
    def _row_count(executed: Any) -> int | None:
        # Most Ibis backends return a pandas DataFrame; some return a
        # PyArrow Table. Both expose len().
        try:
            return len(executed)
        except TypeError:
            return None
