"""Tests for :class:`ElandSource`.

Construction-time guards run with no Elasticsearch dependency. End-to-end
processing is exercised by monkey-patching ``eland.DataFrame`` so the
test does not need a live cluster.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.specialized.eland.eland_dataframe import ElandDataFrame
from pirn.domains.data.specialized.eland.eland_source import ElandSource
from pirn.tapestry import Tapestry


class _StubEsClient:
    """Stand-in for ``elasticsearch.Elasticsearch``."""

    def __init__(self, name: str = "es") -> None:
        self.name = name


class TestElandSourceConstruction:
    def test_rejects_none_client(self) -> None:
        with Tapestry():
            with pytest.raises(ValueError, match="es_client"):
                ElandSource(es_client=None, index="orders", _config=KnotConfig(id="src"))

    def test_rejects_empty_index(self) -> None:
        with Tapestry():
            with pytest.raises(ValueError, match="non-empty"):
                ElandSource(
                    es_client=_StubEsClient(), index="", _config=KnotConfig(id="src"),
                )

    def test_rejects_non_string_index(self) -> None:
        with Tapestry():
            with pytest.raises(ValueError, match="non-empty"):
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


@pytest.mark.asyncio
class TestElandSourceProcess:
    async def test_emits_eland_dataframe_via_stubbed_eland(self, monkeypatch) -> None:
        pytest.importorskip("eland")
        import eland as ed

        captured: dict[str, Any] = {}

        class _FakeFrame:
            def __init__(self, *, es_client: Any, es_index_pattern: str) -> None:
                captured["es_client"] = es_client
                captured["es_index_pattern"] = es_index_pattern

        monkeypatch.setattr(ed, "DataFrame", _FakeFrame)
        client = _StubEsClient()

        with Tapestry() as t:
            ElandSource(es_client=client, index="orders", _config=KnotConfig(id="src"))
        result = await t.run(RunRequest())

        emitted = result.outputs["src"]
        assert isinstance(emitted, ElandDataFrame)
        assert emitted.source_uri == "elasticsearch://orders"
        assert captured["es_client"] is client
        assert captured["es_index_pattern"] == "orders"
