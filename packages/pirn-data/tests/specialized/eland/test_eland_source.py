"""Tests for :class:`ElandSource`.

Construction-time guards are gone; validation now lives in ``process()``.
End-to-end processing is exercised by monkey-patching ``eland.DataFrame``
so the test does not need a live cluster.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specialized.eland.eland_dataframe import ElandDataFrame
from pirn_data.specialized.eland.eland_source import ElandSource
from pirn_data.specialized.eland.elasticsearch_connection import (
    ElasticsearchConnection,
)
from pirn_data.specialized.eland.elasticsearch_connection_knot import (
    ElasticsearchConnectionKnot,
)


class _StubEsClient:
    """Stand-in for ``elasticsearch.Elasticsearch``."""

    def __init__(self, name: str = "es") -> None:
        self.name = name


class TestElandSourceValidation(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_empty_index(self) -> None:
        client = _StubEsClient()
        conn = ElasticsearchConnection(client=client)
        src = object.__new__(ElandSource)
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await ElandSource.process(src, connection=conn, index="")

    async def test_process_rejects_non_string_index(self) -> None:
        client = _StubEsClient()
        conn = ElasticsearchConnection(client=client)
        src = object.__new__(ElandSource)
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await ElandSource.process(src, connection=conn, index=123)  # type: ignore[arg-type]


class TestElandSourceProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_eland_dataframe_via_stubbed_eland(self) -> None:
        try:
            import eland as ed
        except ImportError:
            self.skipTest("eland not installed")
            return

        captured: dict[str, Any] = {}

        class _FakeFrame:
            def __init__(self, *, es_client: Any, es_index_pattern: str) -> None:
                captured["es_client"] = es_client
                captured["es_index_pattern"] = es_index_pattern

        client = _StubEsClient()
        with unittest.mock.patch.object(ed, "DataFrame", _FakeFrame):
            with Tapestry() as t:
                conn_knot = ElasticsearchConnectionKnot(
                    es_client=client, _config=KnotConfig(id="es_conn")
                )
                ElandSource(connection=conn_knot, index="orders", _config=KnotConfig(id="src"))
            result = await t.run(RunRequest())

        emitted = result.outputs["src"]
        assert isinstance(emitted, ElandDataFrame)
        assert emitted.source_uri == "elasticsearch://orders"
        assert captured["es_client"] is client
        assert captured["es_index_pattern"] == "orders"
