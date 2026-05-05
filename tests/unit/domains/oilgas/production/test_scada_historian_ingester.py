"""Unit tests for :class:`ScadaHistorianIngester`."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.scada_historian_ingester import (
    ScadaHistorianIngester,
)
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):

    def setUp(self) -> None:
        from tests.unit.domains.oilgas.conftest import StubHistorianConnection
        self.stub_historian = StubHistorianConnection()
        from datetime import datetime, timezone
        self.fixed_since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    def test_rejects_non_historian_connection(self) -> None:
        with self.assertRaisesRegex(TypeError, "connection"):
            ScadaHistorianIngester(
                connection="not-a-conn",  # type: ignore[arg-type]
                tag="tag",
                since=self.fixed_since,
                sample_interval_sec=60.0,
                _config=KnotConfig(id="i"),
            )

    def test_rejects_empty_tag(self) -> None:
        with self.assertRaisesRegex(ValueError, "tag"):
            ScadaHistorianIngester(
                connection=self.stub_historian,  # type: ignore[arg-type]
                tag="",
                since=self.fixed_since,
                sample_interval_sec=60.0,
                _config=KnotConfig(id="i"),
            )

    def test_rejects_non_datetime_since(self) -> None:
        with self.assertRaisesRegex(TypeError, "since"):
            ScadaHistorianIngester(
                connection=self.stub_historian,  # type: ignore[arg-type]
                tag="tag",
                since="2026-01-01",  # type: ignore[arg-type]
                sample_interval_sec=60.0,
                _config=KnotConfig(id="i"),
            )

    def test_rejects_non_positive_interval(self) -> None:
        with self.assertRaisesRegex(ValueError, "sample_interval_sec"):
            ScadaHistorianIngester(
                connection=self.stub_historian,  # type: ignore[arg-type]
                tag="tag",
                since=self.fixed_since,
                sample_interval_sec=0.0,
                _config=KnotConfig(id="i"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        from tests.unit.domains.oilgas.conftest import StubHistorianConnection
        self.stub_historian = StubHistorianConnection()
        from datetime import datetime, timezone
        self.fixed_since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    async def test_returns_series(self) -> None:
        with Tapestry() as t:
            ScadaHistorianIngester(
                connection=self.stub_historian,  # type: ignore[arg-type]
                tag="P:WELL1.OILRATE",
                since=self.fixed_since,
                sample_interval_sec=60.0,
                _config=KnotConfig(id="i"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["i"]
        assert isinstance(out, ScadaTimeSeries)
        assert out.sensor_id == "P:WELL1.OILRATE"
        assert out.sample_interval_sec == 60.0
