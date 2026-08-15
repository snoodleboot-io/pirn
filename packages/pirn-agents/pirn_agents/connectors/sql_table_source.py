"""``SqlTableSource`` — core's ``TableSource`` capability over a SQL connector (PIR-722).

Adapts a query-driven :class:`~pirn_agents.tools.sql.sql_connector.SqlConnector`
to core's :class:`~pirn.connectors.capabilities.table_source.TableSource`
capability, so a whole-table SQL scan can be consumed by any knot that accepts a
``TableSource`` — alongside Stripe, Salesforce, GitHub issues or any other
vendor implementing the same capability, with no consumer-side knowledge of
where the rows came from.

**This is a facade, not a widening of ``SqlConnector``.** ``SqlConnector`` is
query-driven: the caller supplies the SQL. ``TableSource.fetch_page`` has no
query parameter at all. The two are deliberately *not* merged — instead this
class binds one table at construction and derives the statement itself, which is
the only shape in which a query-driven backend can honestly satisfy a
query-less capability. ``SqlConnector`` itself is untouched.

**Identifier quoting.** The bound table name is interpolated into SQL, because
no dialect binds an identifier as a parameter. That decision — validate against
a portable allowlist, then double-quote — lives in
:class:`~pirn_agents.connectors.sql_identifier.SqlIdentifier`, which is applied
to the table and to every ``order_by`` column at construction time, so a hostile
name is refused before any statement is built. Read that module for the full
reasoning.

**Why no bound parameters at all.** ``SqlConnector.execute`` accepts
``parameters`` but declares no paramstyle, and the shipped backends disagree:
SQLite binds ``?`` while asyncpg binds ``$1``. A facade that must work against
any ``SqlConnector`` therefore cannot emit a placeholder. ``LIMIT`` and
``OFFSET`` are instead rendered from Python ``int`` values that this class
derives itself — a validated page size and an offset parsed out of the cursor —
so the interpolated text is an integer by construction and carries no attacker
influence. The cursor is checked to be an ASCII decimal string before parsing,
so a hostile cursor is rejected rather than reaching the database.

**Pagination model.** The cursor is the opaque encoding of a ``LIMIT``/``OFFSET``
row offset. Each call fetches ``page_size + 1`` rows: the extra probe row decides
whether a further page exists, so a table whose length is an exact multiple of
the page size correctly ends the stream instead of handing back a cursor that
would fetch an empty page. The probe row is trimmed before the page is returned.

Two caveats a caller must know:

* **Ordering.** ``OFFSET`` pagination is only stable under a deterministic row
  order. Pass ``order_by`` naming a unique key for a scan that must not repeat
  or skip rows; with no ``order_by`` the statement omits ``ORDER BY`` entirely
  and the row order is whatever the backend returns, which is well-defined only
  for a quiescent table.
* **Row caps.** A connector may cap its own result set —
  :class:`~pirn_agents.connectors.sql_service_connector.SqlServiceConnector`
  truncates to ``max_rows``. That cap is not visible through the ``SqlConnector``
  interface (correctly: it is not part of the contract), so if ``page_size + 1``
  exceeds it the probe row is eaten and the scan ends a page early. Keep
  ``page_size`` comfortably below the connector's cap.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.connectors.capabilities.table_source import TableSource

from pirn_agents.connectors.sql_identifier import SqlIdentifier
from pirn_agents.tools.sql.sql_connector import SqlConnector


class SqlTableSource(TableSource):
    """Paginated whole-table scans of one bound SQL table, as a ``TableSource``."""

    def __init__(
        self,
        *,
        connector: SqlConnector,
        table: str,
        page_size: int = 100,
        order_by: Sequence[str] | None = None,
    ) -> None:
        """Bind the facade to one connector and one table.

        Args:
            connector: The SQL backend every page is read through.
            table: The table to scan, optionally ``schema``-qualified. Validated
                and quoted by :class:`SqlIdentifier`.
            page_size: Rows per page when the caller does not override it.
            order_by: Optional column names for a deterministic scan order; each
                is validated and quoted by :class:`SqlIdentifier`.

        Raises:
            TypeError: If ``connector`` is not a :class:`SqlConnector`.
            ValueError: If ``page_size`` is not positive, or ``table`` or any
                ``order_by`` column is not a portable SQL identifier.
        """
        if not isinstance(connector, SqlConnector):
            raise TypeError(
                f"SqlTableSource: connector must be a SqlConnector, got {type(connector).__name__}"
            )
        self._table = SqlIdentifier(table)
        self._order_by = tuple(SqlIdentifier(column) for column in order_by or ())
        self._page_size = self._validated_page_size(page_size)
        self._connector = connector

    async def fetch_page(
        self,
        cursor: str | None = None,
        *,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Fetch one page of rows from the bound table.

        Args:
            cursor: Opaque token from the previous call, or ``None`` to start a
                new scan.
            page_size: Rows for this page; falls back to the bound default.

        Returns:
            ``(rows, next_cursor)`` — column-keyed row mappings and the cursor
            for the following page, or ``None`` once the scan is exhausted.

        Raises:
            TypeError: If ``cursor`` is neither a ``str`` nor ``None``.
            ValueError: If ``cursor`` is not an ASCII decimal offset, or
                ``page_size`` is not positive.
        """
        offset = self._offset_from_cursor(cursor)
        size = self._page_size if page_size is None else self._validated_page_size(page_size)
        columns, fetched = await self._connector.execute(
            self._render_query(limit=size + 1, offset=offset)
        )
        rows = list(fetched)
        page: list[Mapping[str, Any]] = [
            dict(zip(columns, row, strict=False)) for row in rows[:size]
        ]
        next_cursor = str(offset + size) if len(rows) > size else None
        return page, next_cursor

    def _render_query(self, *, limit: int, offset: int) -> str:
        """Render the placeholder-free scan statement for one page.

        ``limit`` and ``offset`` are ``int`` by construction (a validated page
        size and a digits-only cursor), so interpolating them cannot inject; the
        table and column names are pre-validated :class:`SqlIdentifier` values.
        """
        ordering = ""
        if self._order_by:
            ordering = " ORDER BY " + ", ".join(column.sql for column in self._order_by)
        return f"SELECT * FROM {self._table.sql}{ordering} LIMIT {limit} OFFSET {offset}"

    def _offset_from_cursor(self, cursor: str | None) -> int:
        """Parse a cursor into a non-negative row offset, rejecting anything else."""
        if cursor is None:
            return 0
        if not isinstance(cursor, str):
            raise TypeError(
                f"SqlTableSource: cursor must be a str or None, got {type(cursor).__name__}"
            )
        # ASCII-only digits: str.isdigit() alone accepts Arabic-Indic and other
        # Unicode decimal forms, and would also let a signed, spaced or
        # exponent-bearing string through to int().
        if not cursor.isascii() or not cursor.isdigit():
            raise ValueError(
                "SqlTableSource: cursor must be an ASCII decimal row offset returned by a "
                "previous fetch_page() call"
            )
        return int(cursor)

    @staticmethod
    def _validated_page_size(page_size: int) -> int:
        """Return ``page_size`` if it is a positive row count, else raise."""
        if page_size <= 0:
            raise ValueError(f"SqlTableSource: page_size must be positive, got {page_size}")
        return page_size
