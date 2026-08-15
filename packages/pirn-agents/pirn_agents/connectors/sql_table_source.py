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

import re
from collections.abc import Mapping, Sequence
from re import Pattern
from typing import Any, ClassVar

from pirn.connectors.capabilities.table_source import TableSource

from pirn_agents.connectors.sql_identifier import SqlIdentifier
from pirn_agents.tools.sql.sql_connector import SqlConnector


class SqlTableSource(TableSource):
    """Paginated whole-table scans of one bound SQL table, as a ``TableSource``.

    Instances are immutable. The table and ``order_by`` columns are validated once,
    at construction, so a writable attribute would reopen the hole the allowlist
    closes: ``_table`` was previously replaceable with any object exposing a
    ``.sql`` string, which the renderer then interpolated verbatim. Writes are
    refused by ``__setattr__``, and — the stronger half — the identifier portion of
    the statement is rendered once at construction, so even a write that reaches
    past ``__setattr__`` cannot change the SQL that is emitted.

    ``__slots__`` is declared for intent and to keep the state enumerated, but note
    it cannot stand alone here: ``TableSource`` is a plain class, so instances still
    carry a ``__dict__`` and ``__setattr__`` is what actually refuses new attributes.
    """

    __slots__ = ("_connector", "_order_by", "_page_size", "_scan_prefix", "_table")

    _table: SqlIdentifier
    _order_by: tuple[SqlIdentifier, ...]
    _page_size: int
    _connector: SqlConnector
    _scan_prefix: str

    # Ceiling on a single page, in rows. An internal class attribute rather than a
    # module constant so a deployment with a genuinely larger appetite can subclass
    # instead of editing this module; see _validated_page_size for why a cap exists.
    _maximum_page_size: ClassVar[int] = 1_000_000

    # A whole cursor: ASCII digits only. See _offset_from_cursor for why this is a
    # regex and not str.isdigit()/isascii().
    _cursor_pattern: ClassVar[Pattern[str]] = re.compile(r"[0-9]+")

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
            TypeError: If ``connector`` is not a :class:`SqlConnector`, or
                ``page_size`` is not exactly an ``int``.
            ValueError: If ``page_size`` is out of range, or ``table`` or any
                ``order_by`` column is not a portable SQL identifier.
        """
        if not isinstance(connector, SqlConnector):
            raise TypeError(
                f"SqlTableSource: connector must be a SqlConnector, got {type(connector).__name__}"
            )
        bound_table = SqlIdentifier(table)
        columns = tuple(SqlIdentifier(column) for column in order_by or ())
        ordering = ""
        if columns:
            ordering = " ORDER BY " + ", ".join(column.sql for column in columns)
        # object.__setattr__ because this class's own __setattr__ refuses writes.
        object.__setattr__(self, "_table", bound_table)
        object.__setattr__(self, "_order_by", columns)
        object.__setattr__(self, "_page_size", self._validated_page_size(page_size))
        object.__setattr__(self, "_connector", connector)
        # Render the invariant head of the statement once, here, while the
        # validated identifiers are in hand. Everything that reaches SQL from now
        # on is either this frozen string or an int, so no later state change can
        # alter the emitted text.
        object.__setattr__(self, "_scan_prefix", f"SELECT * FROM {bound_table.sql}{ordering}")

    def __setattr__(self, name: str, value: object) -> None:
        """Refuse every attribute write: the bound table and page size are final."""
        raise AttributeError(
            f"SqlTableSource is immutable; cannot set {name!r}. The table and order-by "
            "columns are validated once at construction, so rebinding them would bypass "
            "the identifier allowlist. Construct a new SqlTableSource instead."
        )

    def __delattr__(self, name: str) -> None:
        """Refuse every attribute deletion, for the same reason as ``__setattr__``."""
        raise AttributeError(f"SqlTableSource is immutable; cannot delete {name!r}")

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
            TypeError: If ``cursor`` is neither a ``str`` nor ``None``, or
                ``page_size`` is not exactly an ``int``.
            ValueError: If ``cursor`` is not an ASCII decimal offset, or
                ``page_size`` is out of range.
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

        The identifier half of the statement is not rebuilt here: it was rendered
        at construction, from identifiers validated at construction, and is
        interpolated as a fixed string. Re-reading ``self._table`` per call would
        mean the emitted SQL depended on live attribute state, which is what made
        a post-construction swap of ``_table`` injectable.

        ``limit`` and ``offset`` arrive already validated — an exact-``int`` page
        size and a digits-only cursor — and are nevertheless passed through
        ``int()`` here. That is deliberate belt-and-braces: an f-string renders a
        value by calling its ``__format__``, so a lying object that reached this
        point would write its own SQL, whereas ``int()`` must return a true
        integer whatever ``__int__`` does. Validation is the defence; this makes
        the rendering safe even if a future edit routes around it.
        """
        return f"{self._scan_prefix} LIMIT {int(limit)} OFFSET {int(offset)}"

    def _offset_from_cursor(self, cursor: str | None) -> int:
        """Parse a cursor into a non-negative row offset, rejecting anything else.

        Matching is done with a regex rather than ``str`` predicates. ``isascii``
        and ``isdigit`` are methods on the caller's object, and ``isinstance``
        admits ``str`` subclasses, so a subclass overriding them could vouch for a
        buffer they do not describe — after which ``int()`` raised CPython's own
        ``ValueError``, which quotes the offending string and so carried the
        payload into the logs. ``re`` reads the honest buffer, and the offset is
        parsed from ``match.group()``, which is an exact ``str`` of ASCII digits
        and therefore cannot fail to parse or echo anything.

        ``[0-9]`` rather than ``\\d``: the latter also matches Arabic-Indic and
        other Unicode decimal forms, which ``int()`` would happily accept.
        """
        if cursor is None:
            return 0
        if not isinstance(cursor, str):
            raise TypeError(
                f"SqlTableSource: cursor must be a str or None, got {type(cursor).__name__}"
            )
        match = self._cursor_pattern.fullmatch(cursor)
        if match is None:
            raise ValueError(
                "SqlTableSource: cursor must be an ASCII decimal row offset returned by a "
                "previous fetch_page() call"
            )
        return int(match.group())

    @classmethod
    def _validated_page_size(cls, page_size: int) -> int:
        """Return ``page_size`` if it is a plain, in-range ``int``, else raise.

        The type check is a security control, not defensive tidiness. ``page_size``
        is interpolated into the statement text, and an f-string renders a value by
        calling its ``__format__`` — which any object may override to return
        arbitrary SQL while its arithmetic and comparisons behave normally. An
        ``isinstance`` check does not close that: ``bool`` and any hostile ``int``
        subclass pass it. Only exact ``int`` is accepted, so the rendered text is a
        Python integer literal and nothing else. ``bool`` is refused rather than
        read as 0/1 because a flag reaching this parameter is a caller mistake, not
        a one-row page.

        The upper bound exists because every row of a page is materialised in
        memory as a ``dict`` before being returned, and the statement is built from
        the number given. An unbounded page size therefore lets a single call ask a
        backend for an arbitrarily large result set and allocate without limit — a
        memory-exhaustion foot-gun reachable from any caller-supplied value, such
        as a JSON payload or an LLM tool-call argument.

        Raises:
            TypeError: If ``page_size`` is not exactly an ``int`` (``bool``,
                ``float``, ``Decimal`` and ``int`` subclasses are all refused).
            ValueError: If ``page_size`` is not positive or exceeds the cap.
        """
        # `type(...) is int` rather than isinstance: subclasses are the attack.
        if type(page_size) is not int:
            raise TypeError(
                "SqlTableSource: page_size must be an int, got "
                f"{type(page_size).__name__}"  # the type, never the value
            )
        if page_size <= 0:
            raise ValueError("SqlTableSource: page_size must be a positive row count")
        if page_size > cls._maximum_page_size:
            raise ValueError(f"SqlTableSource: page_size must not exceed {cls._maximum_page_size}")
        return page_size
