"""Tests for :class:`StampBronzeMetadataKnot`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.medallion.stamp_bronze_metadata_knot import (
    StampBronzeMetadataKnot,
)


def _make_knot(source_uri: str = "db://src/orders") -> StampBronzeMetadataKnot:
    return StampBronzeMetadataKnot(
        rows=MagicMock(),
        source_uri=source_uri,
        _config=KnotConfig(id="stamp"),
    )


class TestStampBronzeMetadataKnot(unittest.IsolatedAsyncioTestCase):
    async def test_appends_metadata_to_each_row(self) -> None:
        k = _make_knot()
        result = await k.process(rows=[(1, "alice"), (2, "bob")], source_uri="db://src/orders")
        assert len(result) == 2
        for stamped in result:
            assert len(stamped) == 4
            assert stamped[-1] == "db://src/orders"

    async def test_ingested_at_is_iso_string(self) -> None:
        k = _make_knot()
        result = await k.process(rows=[(42,)], source_uri="db://src/orders")
        ingested_at = result[0][-2]
        assert isinstance(ingested_at, str)
        assert "T" in ingested_at

    async def test_empty_rows_returns_empty_list(self) -> None:
        k = _make_knot()
        result = await k.process(rows=[], source_uri="db://src/orders")
        assert result == []


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_source_uri_from_upstream_knot(self) -> None:
        @knot
        async def emit_rows() -> list:
            return [(1, "alice")]

        @knot
        async def emit_uri() -> str:
            return "db://src/t"

        with Tapestry() as t:
            r = emit_rows(_config=KnotConfig(id="rows"))
            u = emit_uri(_config=KnotConfig(id="uri"))
            k = StampBronzeMetadataKnot(
                rows=r, source_uri=u, _config=KnotConfig(id="stamp")
            )
        result = await t.run(RunRequest())
        stamped = result.outputs[k.config.id]
        assert stamped[0][-1] == "db://src/t"


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> StampBronzeMetadataKnot:
        defaults: dict[str, Any] = {"source_uri": "db://src/t"}
        defaults.update(kwargs)
        with Tapestry():
            return StampBronzeMetadataKnot(
                rows=MagicMock(), **defaults, _config=KnotConfig(id="val")
            )

    async def _call(self, k: StampBronzeMetadataKnot, **overrides: Any) -> None:
        args: dict[str, Any] = {"rows": [], "source_uri": "db://src/t"}
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_empty_source_uri(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_uri"):
            await self._call(k, source_uri="")

    async def test_rejects_non_string_source_uri(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_uri"):
            await self._call(k, source_uri=None)
