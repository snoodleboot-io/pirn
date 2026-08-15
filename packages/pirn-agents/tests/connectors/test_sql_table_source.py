"""Tests for :class:`SqlTableSource`, the bound-table ``TableSource`` facade.

The facade adapts a query-driven :class:`SqlConnector` to core's paginated
:class:`~pirn.connectors.capabilities.table_source.TableSource` capability for
whole-table scans. These tests pin the emitted SQL (including the ``page_size + 1``
probe row that decides ``next_cursor``), the row-mapping shape, cursor round-trip,
and that a hostile cursor cannot reach the database.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import closing
from decimal import Decimal
from typing import Any

import pytest
from pirn.connectors.capabilities.table_source import TableSource

from pirn_agents.connectors.sql_identifier import SqlIdentifier
from pirn_agents.connectors.sql_service_connector import SqlServiceConnector
from pirn_agents.connectors.sql_table_source import SqlTableSource
from pirn_agents.tools.sql.sql_connector import SqlConnector


class _FakeSqlConnector(SqlConnector):
    """Offline :class:`SqlConnector` double recording queries; returns fixed results."""

    def __init__(self, columns: Sequence[str] = (), rows: Sequence[Sequence[Any]] = ()) -> None:
        self._columns = list(columns)
        self._rows = [list(row) for row in rows]
        self.calls: list[tuple[str, Sequence[Any] | None]] = []

    async def execute(
        self, query: str, parameters: Sequence[Any] | None = None
    ) -> tuple[Sequence[str], Sequence[Sequence[Any]]]:
        self.calls.append((query, parameters))
        return self._columns, [list(row) for row in self._rows]


def _rows(count: int) -> list[list[Any]]:
    return [[n, f"name-{n}"] for n in range(count)]


class _LyingPageSize(int):
    """An ``int`` subclass that injects SQL through ``__format__``.

    ``isinstance(x, int)`` is true, so a subclass check alone lets this through;
    the payload is only delivered when the value is interpolated by an f-string,
    which consults ``__format__`` rather than the integer's own value.
    """

    def __format__(self, format_spec: str) -> str:
        return "1 OFFSET (SELECT CASE WHEN substr(pw,1,1)='h' THEN 4 ELSE 0 END FROM secrets) -- "

    def __add__(self, other: int) -> _LyingPageSize:
        """Absorb the ``+ 1`` probe-row arithmetic so the payload survives."""
        return self


class _NegativePageSize(int):
    """An ``int`` subclass that renders a negative, comment-terminated ``LIMIT``."""

    def __format__(self, format_spec: str) -> str:
        return "-1 --"

    def __add__(self, other: int) -> _NegativePageSize:
        return self


class _DuckTypedPageSize:
    """A non-``int`` that satisfies every operation the unhardened code performed."""

    def __le__(self, other: object) -> bool:
        """Claim to be greater than zero so a ``<= 0`` range check passes."""
        return False

    def __add__(self, other: int) -> _DuckTypedPageSize:
        return self

    def __format__(self, format_spec: str) -> str:
        return "1 UNION SELECT pw FROM secrets--"


class _HostileIdentifier:
    """Anything exposing ``.sql`` was interpolated verbatim if swapped in post-hoc."""

    @property
    def sql(self) -> str:
        return '"users"; DROP TABLE secrets; --'


class TestCapabilityWiring:
    def test_is_a_table_source(self) -> None:
        source = SqlTableSource(connector=_FakeSqlConnector(), table="users")
        assert isinstance(source, TableSource)

    def test_rejects_a_non_connector(self) -> None:
        with pytest.raises(TypeError, match="SqlTableSource"):
            SqlTableSource(connector=object(), table="users")  # pyright: ignore[reportArgumentType]

    def test_rejects_a_hostile_table_name_at_construction(self) -> None:
        with pytest.raises(ValueError, match="SqlIdentifier"):
            SqlTableSource(connector=_FakeSqlConnector(), table="users; DROP TABLE users")

    def test_rejects_a_hostile_order_by_column_at_construction(self) -> None:
        with pytest.raises(ValueError, match="SqlIdentifier"):
            SqlTableSource(connector=_FakeSqlConnector(), table="users", order_by=["id; DROP x"])

    @pytest.mark.parametrize("size", [0, -1])
    def test_rejects_a_non_positive_page_size(self, size: int) -> None:
        with pytest.raises(ValueError, match="page_size"):
            SqlTableSource(connector=_FakeSqlConnector(), table="users", page_size=size)


class TestEmittedSql:
    async def test_first_page_selects_the_quoted_table_with_a_probe_row(self) -> None:
        connector = _FakeSqlConnector(["id", "name"], _rows(2))
        source = SqlTableSource(connector=connector, table="public.users", page_size=3)
        await source.fetch_page()
        assert connector.calls[0][0] == 'SELECT * FROM "public"."users" LIMIT 4 OFFSET 0'

    async def test_order_by_columns_are_quoted(self) -> None:
        connector = _FakeSqlConnector(["id"], _rows(1))
        source = SqlTableSource(
            connector=connector, table="users", page_size=2, order_by=["id", "created_at"]
        )
        await source.fetch_page()
        assert connector.calls[0][0] == (
            'SELECT * FROM "users" ORDER BY "id", "created_at" LIMIT 3 OFFSET 0'
        )

    async def test_no_bound_parameters_are_sent(self) -> None:
        # SqlConnector declares no paramstyle (SQLite binds "?", asyncpg binds
        # "$1"), so the facade must emit a placeholder-free statement.
        connector = _FakeSqlConnector(["id"], _rows(1))
        source = SqlTableSource(connector=connector, table="users")
        await source.fetch_page()
        query, parameters = connector.calls[0]
        assert parameters is None
        assert "?" not in query
        assert "$" not in query

    async def test_per_call_page_size_overrides_the_default(self) -> None:
        connector = _FakeSqlConnector(["id"], _rows(1))
        source = SqlTableSource(connector=connector, table="users", page_size=50)
        await source.fetch_page(page_size=2)
        assert connector.calls[0][0].endswith("LIMIT 3 OFFSET 0")

    async def test_rejects_a_non_positive_per_call_page_size(self) -> None:
        source = SqlTableSource(connector=_FakeSqlConnector(), table="users")
        with pytest.raises(ValueError, match="page_size"):
            await source.fetch_page(page_size=0)


class TestRowsAndPagination:
    async def test_rows_are_column_keyed_mappings(self) -> None:
        connector = _FakeSqlConnector(["id", "name"], _rows(2))
        source = SqlTableSource(connector=connector, table="users", page_size=5)
        rows, next_cursor = await source.fetch_page()
        assert rows == [{"id": 0, "name": "name-0"}, {"id": 1, "name": "name-1"}]
        assert next_cursor is None

    async def test_a_short_page_ends_the_stream(self) -> None:
        connector = _FakeSqlConnector(["id", "name"], _rows(2))
        source = SqlTableSource(connector=connector, table="users", page_size=3)
        rows, next_cursor = await source.fetch_page()
        assert len(rows) == 2
        assert next_cursor is None

    async def test_an_exactly_full_page_ends_the_stream(self) -> None:
        # The probe row is what makes this correct: a page holding exactly
        # page_size rows is the last page, and must not hand back a cursor
        # that would fetch an empty page.
        connector = _FakeSqlConnector(["id", "name"], _rows(3))
        source = SqlTableSource(connector=connector, table="users", page_size=3)
        rows, next_cursor = await source.fetch_page()
        assert len(rows) == 3
        assert next_cursor is None

    async def test_a_full_page_plus_probe_yields_a_cursor_and_trims_the_probe(self) -> None:
        connector = _FakeSqlConnector(["id", "name"], _rows(4))
        source = SqlTableSource(connector=connector, table="users", page_size=3)
        rows, next_cursor = await source.fetch_page()
        assert len(rows) == 3
        assert next_cursor == "3"

    async def test_cursor_round_trip_advances_the_offset(self) -> None:
        connector = _FakeSqlConnector(["id", "name"], _rows(4))
        source = SqlTableSource(connector=connector, table="users", page_size=3)
        _, next_cursor = await source.fetch_page()
        await source.fetch_page(next_cursor)
        assert connector.calls[1][0].endswith("LIMIT 4 OFFSET 3")

    async def test_an_empty_table_yields_no_rows_and_no_cursor(self) -> None:
        source = SqlTableSource(connector=_FakeSqlConnector(["id"], []), table="users")
        rows, next_cursor = await source.fetch_page()
        assert rows == []
        assert next_cursor is None

    async def test_extra_row_values_beyond_the_columns_are_dropped(self) -> None:
        connector = _FakeSqlConnector(["id"], [[1, "surplus"]])
        source = SqlTableSource(connector=connector, table="users")
        rows, _ = await source.fetch_page()
        assert rows == [{"id": 1}]


class TestHostileCursorsAreRejected:
    @pytest.mark.parametrize(
        "cursor",
        [
            "0; DROP TABLE users",
            "1 UNION SELECT password FROM secrets",
            "-1",
            "abc",
            "",
            "   ",
            "1.5",
            "0x10",
            "1e3",
            "+1",
            " 1 ",
        ],
    )
    async def test_rejected_before_reaching_the_connector(self, cursor: str) -> None:
        connector = _FakeSqlConnector(["id"], _rows(1))
        source = SqlTableSource(connector=connector, table="users")
        with pytest.raises(ValueError, match="cursor"):
            await source.fetch_page(cursor)
        assert connector.calls == []

    async def test_non_string_cursor_is_rejected(self) -> None:
        source = SqlTableSource(connector=_FakeSqlConnector(), table="users")
        with pytest.raises(TypeError, match="cursor"):
            await source.fetch_page(7)  # pyright: ignore[reportArgumentType]


class TestHostilePageSizesAreRejected:
    """``page_size`` reaches the statement text, so its type is a security control.

    ``LIMIT``/``OFFSET`` cannot be bound as parameters here (the facade must work
    against any ``SqlConnector`` and the backends disagree on paramstyle), so the
    page size is interpolated. An f-string calls ``__format__``, which any object
    may override — including an ``int`` subclass, which passes ``isinstance``. A
    range check alone is therefore not a defence: these tests pin that a hostile
    or merely wrong-typed page size is refused *before* any statement is built.
    """

    @pytest.mark.parametrize(
        "size",
        [
            pytest.param(_LyingPageSize(1), id="int-subclass-lying-format"),
            pytest.param(_NegativePageSize(1), id="int-subclass-negative-format"),
            pytest.param(_DuckTypedPageSize(), id="duck-typed-le-and-add"),
            pytest.param(100.0, id="float"),
            pytest.param(True, id="bool"),
            pytest.param(Decimal(5), id="decimal"),
            pytest.param(10**30, id="absurdly-large-int"),
        ],
    )
    async def test_no_sql_is_emitted_for_a_hostile_page_size(self, size: Any) -> None:
        connector = _FakeSqlConnector(["id"], _rows(1))
        source = SqlTableSource(connector=connector, table="users")
        with pytest.raises((TypeError, ValueError), match="page_size"):
            await source.fetch_page(page_size=size)
        assert connector.calls == []

    @pytest.mark.parametrize(
        "size",
        [
            pytest.param(_LyingPageSize(1), id="int-subclass-lying-format"),
            pytest.param(_DuckTypedPageSize(), id="duck-typed-le-and-add"),
            pytest.param(100.0, id="float"),
            pytest.param(True, id="bool"),
            pytest.param(Decimal(5), id="decimal"),
        ],
    )
    def test_a_wrongly_typed_page_size_is_refused_at_construction(self, size: Any) -> None:
        with pytest.raises(TypeError, match="page_size"):
            SqlTableSource(connector=_FakeSqlConnector(), table="users", page_size=size)

    def test_bool_is_not_accepted_as_the_int_it_subclasses(self) -> None:
        # bool is a subclass of int, so an isinstance check alone silently reads
        # True as a page size of 1 — a caller passing a flag by mistake would get
        # one-row pages rather than an error.
        with pytest.raises(TypeError, match="page_size"):
            SqlTableSource(connector=_FakeSqlConnector(), table="users", page_size=True)

    def test_an_oversized_page_size_is_refused(self) -> None:
        with pytest.raises(ValueError, match="page_size"):
            SqlTableSource(connector=_FakeSqlConnector(), table="users", page_size=10**30)

    async def test_rejection_messages_never_echo_the_caller_value(self) -> None:
        source = SqlTableSource(connector=_FakeSqlConnector(), table="users")
        with pytest.raises(ValueError) as info:
            await source.fetch_page(page_size=-4242)
        assert "4242" not in str(info.value)


class TestTheBoundTableIsImmutable:
    """The bound table is validated once at construction; it must stay bound.

    ``_table`` was a writable attribute read afresh on every render, so anything
    exposing a ``.sql`` string could be swapped in after a clean construction and
    would be interpolated verbatim — the allowlist bypassed entirely.
    """

    def test_rebinding_the_table_fails(self) -> None:
        source = SqlTableSource(connector=_FakeSqlConnector(), table="users")
        with pytest.raises(AttributeError):
            source._table = SqlIdentifier("other")

    def test_rebinding_the_page_size_fails(self) -> None:
        source = SqlTableSource(connector=_FakeSqlConnector(), table="users")
        with pytest.raises(AttributeError):
            source._page_size = 10**30

    async def test_a_swapped_in_table_object_cannot_change_the_emitted_sql(self) -> None:
        connector = _FakeSqlConnector(["id"], _rows(1))
        source = SqlTableSource(connector=connector, table="users")
        with pytest.raises(AttributeError):
            source._table = _HostileIdentifier()
        await source.fetch_page()
        assert connector.calls[0][0] == 'SELECT * FROM "users" LIMIT 101 OFFSET 0'

    async def test_the_statement_is_fixed_at_construction(self) -> None:
        # Even reaching past __setattr__ (as object.__setattr__ does) must not
        # change the statement: the scan prefix is rendered once, at construction,
        # from the validated identifiers and never recomputed from live state.
        connector = _FakeSqlConnector(["id"], _rows(1))
        source = SqlTableSource(connector=connector, table="users")
        object.__setattr__(source, "_table", _HostileIdentifier())
        await source.fetch_page()
        assert "DROP TABLE" not in connector.calls[0][0]


class TestAgainstALiveSqliteBackend:
    """End-to-end scan against a real database, not a double.

    The doubles above prove the emitted text; only a live backend proves that
    text is *valid SQL*. The table is deliberately named ``order`` — a reserved
    word — so an unquoted rendering would be a syntax error rather than a silent
    pass, and the scan runs through a read-only connector so the generated
    statement is also shown to clear the read-only guard.
    """

    @staticmethod
    def _seed(database: str) -> None:
        """Create and populate the reserved-word table with stdlib sqlite3.

        Seeding does not go through ``SqlServiceConnector``: its ``execute``
        runs via ``ColumnAwarePool.fetch_columns``, which issues no ``commit``,
        so writes made that way are discarded when the pool closes. That is
        sound for a read-first connector and irrelevant to this facade, but it
        makes the connector unusable as a test fixture writer.
        """
        with closing(sqlite3.connect(database)) as connection:
            connection.execute('CREATE TABLE "order" (id INTEGER, name TEXT)')
            connection.executemany(
                'INSERT INTO "order" (id, name) VALUES (?, ?)',
                [(n, f"n-{n}") for n in range(5)],
            )
            connection.commit()

    async def test_paginates_a_reserved_word_table_read_only(self, tmp_path: Any) -> None:
        pytest.importorskip("aiosqlite")
        database = str(tmp_path / "scan.db")
        self._seed(database)

        reader = SqlServiceConnector(driver="aiosqlite", database=database)
        try:
            source = SqlTableSource(connector=reader, table="order", page_size=2, order_by=["id"])
            collected: list[Mapping[str, Any]] = []
            cursor: str | None = None
            pages = 0
            while True:
                rows, cursor = await source.fetch_page(cursor)
                collected.extend(rows)
                pages += 1
                if cursor is None:
                    break
                assert pages < 10, "pagination failed to terminate"
        finally:
            await reader.close()

        assert pages == 3
        assert collected == [{"id": n, "name": f"n-{n}"} for n in range(5)]

    async def test_a_missing_table_surfaces_the_backend_error(self, tmp_path: Any) -> None:
        pytest.importorskip("aiosqlite")
        connector = SqlServiceConnector(driver="aiosqlite", database=str(tmp_path / "empty.db"))
        source = SqlTableSource(connector=connector, table="absent")
        try:
            with pytest.raises(Exception, match="absent"):
                await source.fetch_page()
        finally:
            await connector.close()
