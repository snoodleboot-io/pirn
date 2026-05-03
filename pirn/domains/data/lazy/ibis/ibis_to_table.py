"""``IbisToTable`` — terminal sink that compiles the deferred expression
to SQL (or the backend's plan format), executes it server-side, and
optionally writes the result into a destination table.

This is the only Tier-3 knot that *materialises*. Everything upstream
runs in deferred form. The materialisation result is not propagated back
to the caller as rows by default — that would defeat the push-down — so
the sink returns a small
:class:`pirn.domains.data.lazy.ibis.ibis_execution_receipt.IbisExecutionReceipt`
describing what was executed and where the result went.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ibis.ibis_execution_receipt import IbisExecutionReceipt
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable
from pirn.nodes.sink import Sink


class IbisToTable(Sink):
    """Compile and execute the deferred expression on its backend."""

    def __init__(
        self,
        *,
        batch: Knot,
        connection: Any,
        target_table: str | None = None,
        overwrite: bool = False,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if connection is None:
            raise TypeError("IbisToTable: connection is required")
        if target_table is not None and not isinstance(target_table, str):
            raise TypeError("IbisToTable: target_table must be a string or None")
        if target_table is not None and not target_table:
            raise ValueError("IbisToTable: target_table must be non-empty when set")
        self._connection = connection
        self._target_table = target_table
        self._overwrite = overwrite
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def target_table(self) -> str | None:
        return self._target_table

    async def process(self, batch: IbisTable, **_: Any) -> IbisExecutionReceipt:
        """Compile the deferred Ibis expression to SQL, execute it, and return an execution receipt.

        Args:
            batch: The upstream IbisTable whose deferred expression will be compiled and executed.

        Returns:
            An IbisExecutionReceipt describing the backend, target table, compiled SQL, and row count.
        """
        compiled_sql = str(self._connection.compile(batch.expression))

        row_count: int | None = None
        if self._target_table is None:
            executed = self._connection.execute(batch.expression)
            row_count = self._row_count(executed)
        else:
            self._materialise_to_table(batch)
            count_expr = batch.expression.count()
            row_count = int(self._connection.execute(count_expr))

        return IbisExecutionReceipt(
            backend_name=batch.backend_name,
            target_table=self._target_table,
            compiled_sql=compiled_sql,
            row_count=row_count,
            executed_at=datetime.now(timezone.utc),
        )

    def _materialise_to_table(self, batch: IbisTable) -> None:
        if self._overwrite and self._target_table in self._connection.list_tables():
            self._connection.drop_table(self._target_table)
        self._connection.create_table(self._target_table, batch.expression)

    @staticmethod
    def _row_count(executed: Any) -> int | None:
        # Most Ibis backends return a pandas DataFrame; some return a
        # PyArrow Table. Both expose len().
        try:
            return len(executed)
        except TypeError:
            return None
