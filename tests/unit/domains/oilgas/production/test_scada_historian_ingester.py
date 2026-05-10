"""Unit tests for :class:`ScadaHistorianIngester`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.scada_historian_ingester import ScadaHistorianIngester
from pirn.domains.oilgas.types.scada_payload import ScadaPayload
from tests.unit.domains.oilgas.conftest import StubHistorianConnection

_SINCE = datetime(2026, 1, 1, tzinfo=UTC)
_HISTORIAN = StubHistorianConnection()


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, tag: str = "P:WELL1.OILRATE") -> ScadaHistorianIngester:
        return ScadaHistorianIngester(
            connection=_HISTORIAN,  # type: ignore[arg-type]
            tag=tag,
            since=_SINCE,
            sample_interval_sec=60.0,
            _config=KnotConfig(id="i"),
        )

    async def test_rejects_non_historian_connection(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "connection"):
            await knot.process(
                connection="not-a-conn",  # type: ignore[arg-type]
                tag="P:WELL1.OILRATE",
                since=_SINCE,
                sample_interval_sec=60.0,
            )

    async def test_rejects_empty_tag(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "tag"):
            await knot.process(
                connection=_HISTORIAN,  # type: ignore[arg-type]
                tag="",
                since=_SINCE,
                sample_interval_sec=60.0,
            )

    async def test_rejects_non_datetime_since(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "since"):
            await knot.process(
                connection=_HISTORIAN,  # type: ignore[arg-type]
                tag="P:WELL1.OILRATE",
                since="2026-01-01",  # type: ignore[arg-type]
                sample_interval_sec=60.0,
            )

    async def test_rejects_non_positive_interval(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "sample_interval_sec"):
            await knot.process(
                connection=_HISTORIAN,  # type: ignore[arg-type]
                tag="P:WELL1.OILRATE",
                since=_SINCE,
                sample_interval_sec=0.0,
            )

    async def test_returns_series(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            connection=_HISTORIAN,  # type: ignore[arg-type]
            tag="P:WELL1.OILRATE",
            since=_SINCE,
            sample_interval_sec=60.0,
        )
        assert isinstance(out, ScadaPayload)
        assert out.series.sensor_id == "P:WELL1.OILRATE"
        assert out.series.sample_interval_sec == 60.0
