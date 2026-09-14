"""Every ``RunHistory`` declares the ``RunResult`` it stores and returns, never ``Any``."""

from __future__ import annotations

from typing import Any, get_type_hints

import pytest

from pirn.backends.base.run_history import RunHistory
from pirn.backends.base.run_retention import RunRetention
from pirn.backends.duckdb_history import DuckDBHistory
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.backends.postgres.postgres_history import PostgresHistory
from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_lineage import KnotLineage
from pirn.core.knot_source_record import KnotSourceRecord
from pirn.core.run_result import RunResult

_HISTORIES: list[type[RunHistory]] = [
    RunHistory,
    InMemoryHistory,
    SQLiteHistory,
    DuckDBHistory,
    PostgresHistory,
]
_NAMES: dict[str, Any] = {
    "RunResult": RunResult,
    "KnotLineage": KnotLineage,
    "KnotSourceRecord": KnotSourceRecord,
    "RunRetention": RunRetention,
}


@pytest.mark.parametrize("history", _HISTORIES, ids=lambda h: h.__name__)
class TestRunHistoryResultTypes:
    def test_record_run_takes_a_run_result(self, history: type[RunHistory]) -> None:
        hints = get_type_hints(history.record_run, localns=_NAMES)
        assert hints["result"] is RunResult

    def test_get_run_returns_an_optional_run_result(self, history: type[RunHistory]) -> None:
        hints = get_type_hints(history.get_run, localns=_NAMES)
        assert hints["return"] == RunResult | None

    def test_query_runs_by_actor_returns_run_results(self, history: type[RunHistory]) -> None:
        hints = get_type_hints(history.query_runs_by_actor, localns=_NAMES)
        assert hints["return"] == list[RunResult]

    def test_children_of_returns_run_results(self, history: type[RunHistory]) -> None:
        hints = get_type_hints(history.children_of, localns=_NAMES)
        assert hints["return"] == list[RunResult]
