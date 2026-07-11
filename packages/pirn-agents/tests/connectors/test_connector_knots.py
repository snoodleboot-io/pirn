"""Unit tests for the F16-S5 per-connector vending knots.

Each knot vends its connector once per run (AD-3), returns it unchanged, and
rejects a wrongly-typed value with an ``isinstance`` guard. One end-to-end
Tapestry run proves the same instance is vended through the graph.
"""

from __future__ import annotations

from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.blob_store_knot import BlobStoreKnot
from pirn_agents.connectors.http_connector import HttpConnector
from pirn_agents.connectors.http_search_connector import HttpSearchConnector
from pirn_agents.connectors.local_blob_store import LocalBlobStore
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


class TestHttpConnectorKnot:
    async def test_vends_unchanged(self) -> None:
        connector = HttpConnector(client=object(), resolver=_resolver)
        knot = _make_knot(HttpConnectorKnot, "http")
        assert await knot.process(connector=connector) is connector

    async def test_rejects_wrong_type(self) -> None:
        knot = _make_knot(HttpConnectorKnot, "http")
        with pytest.raises(TypeError, match="HttpConnector"):
            await knot.process(connector=object())  # type: ignore[arg-type]

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

    async def test_rejects_wrong_type(self) -> None:
        knot = _make_knot(SqlConnectorKnot, "sql")
        with pytest.raises(TypeError, match="SqlServiceConnector"):
            await knot.process(connector=object())  # type: ignore[arg-type]


class TestSearchConnectorKnot:
    async def test_vends_unchanged(self) -> None:
        http = HttpConnector(client=object(), resolver=_resolver)
        connector = HttpSearchConnector(http=http, endpoint="https://s.example/api")
        knot = _make_knot(SearchConnectorKnot, "search")
        assert await knot.process(connector=connector) is connector

    async def test_rejects_wrong_type(self) -> None:
        knot = _make_knot(SearchConnectorKnot, "search")
        with pytest.raises(TypeError, match="SearchBackend"):
            await knot.process(connector=object())  # type: ignore[arg-type]


class TestBlobStoreKnot:
    async def test_vends_unchanged(self, tmp_path: Any) -> None:
        store = LocalBlobStore(root=tmp_path)
        knot = _make_knot(BlobStoreKnot, "blob")
        assert await knot.process(store=store) is store

    async def test_rejects_wrong_type(self) -> None:
        knot = _make_knot(BlobStoreKnot, "blob")
        with pytest.raises(TypeError, match="BlobStore"):
            await knot.process(store=object())  # type: ignore[arg-type]
