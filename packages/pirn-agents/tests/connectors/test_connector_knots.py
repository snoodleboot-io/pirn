"""Unit tests for the F16-S5 per-connector vending knots.

Each knot vends its connector once per run (AD-3) and returns it unchanged. A
wrongly-typed value is rejected by the framework's ``validate_io`` at the IO
boundary — the knots are bare passthroughs with no per-knot ``isinstance`` guard,
matching core's canonical vending knots — so the rejection is asserted through an
engine run, not a direct ``process`` call. One end-to-end Tapestry run proves the
same instance is vended through the graph.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.connectors.http_connector import HttpConnector
from pirn_agents.connectors.http_search_connector import HttpSearchConnector
from pirn_agents.connectors.sql_service_connector import SqlServiceConnector
from pirn_agents.http_connector_knot import HttpConnectorKnot
from pirn_agents.search_connector_knot import SearchConnectorKnot
from pirn_agents.sql_connector_knot import SqlConnectorKnot


def _resolver(_host: str) -> str:
    return "93.184.216.34"


def _make_knot(cls: type, knot_id: str) -> Any:
    with Tapestry():
        knot = cls.__new__(cls)
        object.__setattr__(knot, "_config", KnotConfig(id=knot_id))
    return knot


async def _assert_engine_rejects_wrong_type(cls: type[Knot], expected_type: str) -> None:
    """Drive a wrong-typed value through ``cls`` and assert ``validate_io`` rejects it.

    A bare passthrough does not validate on a direct ``process`` call, so the
    guard only fires when the knot runs through the engine. The run must fail with
    a validation error naming the expected vended type.
    """

    @knot
    async def wrong_source() -> object:
        return object()

    with Tapestry() as tapestry:
        source = wrong_source(_config=KnotConfig(id="src"))
        cls(connector=source, _config=KnotConfig(id="vend"))
    result = await tapestry.run(RunRequest())

    assert result.succeeded is False
    records = [r for r in result.exceptions if r.knot_id == "vend"]
    assert records, "expected a validation failure recorded against the vending knot"
    assert records[0].exc_type == "ValidationError"
    assert expected_type in records[0].message


class TestHttpConnectorKnot:
    async def test_vends_unchanged(self) -> None:
        connector = HttpConnector(client=object(), resolver=_resolver)
        knot = _make_knot(HttpConnectorKnot, "http")
        assert await knot.process(connector=connector) is connector

    async def test_engine_rejects_wrong_type(self) -> None:
        await _assert_engine_rejects_wrong_type(HttpConnectorKnot, "HttpConnector")

    async def test_end_to_end_through_tapestry(self) -> None:
        connector = HttpConnector(client=object(), resolver=_resolver)
        with Tapestry() as tapestry:
            HttpConnectorKnot(connector=connector, _config=KnotConfig(id="http"))
        result = await tapestry.run(RunRequest())
        assert result.outputs["http"] is connector


class TestSqlConnectorKnot:
    async def test_vends_unchanged(self) -> None:
        connector = SqlServiceConnector(connection=object())
        knot = _make_knot(SqlConnectorKnot, "sql")
        assert await knot.process(connector=connector) is connector

    async def test_engine_rejects_wrong_type(self) -> None:
        await _assert_engine_rejects_wrong_type(SqlConnectorKnot, "SqlServiceConnector")


class TestSearchConnectorKnot:
    async def test_vends_unchanged(self) -> None:
        http = HttpConnector(client=object(), resolver=_resolver)
        connector = HttpSearchConnector(http=http, endpoint="https://s.example/api")
        knot = _make_knot(SearchConnectorKnot, "search")
        assert await knot.process(connector=connector) is connector

    async def test_engine_rejects_wrong_type(self) -> None:
        await _assert_engine_rejects_wrong_type(SearchConnectorKnot, "SearchBackend")
