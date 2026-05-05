"""Tests for :class:`ElandSource`.

Construction-time guards run with no Elasticsearch dependency. End-to-end
processing is exercised by monkey-patching ``eland.DataFrame`` so the
test does not need a live cluster.
"""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.specialized.eland.eland_dataframe import ElandDataFrame
from pirn.domains.data.specialized.eland.eland_source import ElandSource
from pirn.tapestry import Tapestry


class _StubEsClient:
    """Stand-in for ``elasticsearch.Elasticsearch``."""

    def __init__(self, name: str = "es") -> None:
        self.name = name


class TestElandSourceConstruction(unittest.TestCase):
    def test_rejects_none_client(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "es_client"):
                ElandSource(es_client=None, index="orders", _config=KnotConfig(id="src"))

    def test_rejects_empty_index(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "non-empty"):
                ElandSource(
                    es_client=_StubEsClient(), index="", _config=KnotConfig(id="src"),
                )

    def test_rejects_non_string_index(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "non-empty"):
                ElandSource(
                    es_client=_StubEsClient(), index=123, _config=KnotConfig(id="src"),  # type: ignore[arg-type]
                )

    def test_attributes_are_exposed(self) -> None:
        client = _StubEsClient()
        with Tapestry():
            src = ElandSource(
                es_client=client, index="orders", _config=KnotConfig(id="src"),
            )
        assert src.es_client is client
        assert src.index == "orders"


class TestElandSourceProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_eland_dataframe_via_stubbed_eland(self) -> None:
        try:
            import eland
        except ImportError as _e:
            self.skipTest("eland not installed")
        import eland as ed

        captured: dict[str, Any] = {}

        class _FakeFrame:
            def __init__(self, *, es_client: Any, es_index_pattern: str) -> None:
                captured["es_client"] = es_client
                captured["es_index_pattern"] = es_index_pattern

        client = _StubEsClient()
        with unittest.mock.patch.object(ed, "DataFrame", _FakeFrame):
            with Tapestry() as t:
                ElandSource(es_client=client, index="orders", _config=KnotConfig(id="src"))
            result = await t.run(RunRequest())

        emitted = result.outputs["src"]
        assert isinstance(emitted, ElandDataFrame)
        assert emitted.source_uri == "elasticsearch://orders"
        assert captured["es_client"] is client
        assert captured["es_index_pattern"] == "orders"
