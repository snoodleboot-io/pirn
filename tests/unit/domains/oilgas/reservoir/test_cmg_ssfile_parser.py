"""Unit tests for :class:`CmgSsfileParser`."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.reservoir.cmg_ssfile_parser import CmgSsfileParser
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries

_SSFILE_CONTENT = """\
* CMG IMEX simulation output
* Title: Test case
TIME       OILRATSC   WATRATSC   GASRATSC
0.0        100.0      5.0        50000.0
1.0        98.5       5.2        49200.0
2.0        97.1       5.4        48500.0
3.0        95.8       5.6        47800.0
"""


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(
        self,
        ssfile_path: str = "/x",
        vector_name: str = "OILRATSC",
    ) -> CmgSsfileParser:
        return CmgSsfileParser(
            ssfile_path=ssfile_path,
            vector_name=vector_name,
            _config=KnotConfig(id="cs"),
        )

    async def test_rejects_empty_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "ssfile_path"):
            await knot.process(ssfile_path="", vector_name="OILRATSC")

    async def test_rejects_empty_vector(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "vector_name"):
            await knot.process(ssfile_path="/x", vector_name="")

    async def test_raises_file_not_found(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(FileNotFoundError):
            await knot.process(ssfile_path="/nonexistent_cmg.txt", vector_name="OILRATSC")

    async def test_returns_series(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(_SSFILE_CONTENT)
            path = f.name
        knot = self._make_knot(ssfile_path=path, vector_name="OILRATSC")
        out = await knot.process(ssfile_path=path, vector_name="OILRATSC")
        assert isinstance(out, ScadaTimeSeries)
        assert out.sensor_id == "cmg:OILRATSC"
        assert out.sample_count == 4
        assert out.sample_interval_sec == 86400.0

    async def test_raises_on_missing_vector(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(_SSFILE_CONTENT)
            path = f.name
        knot = self._make_knot(ssfile_path=path, vector_name="MISSING")
        with self.assertRaises(KeyError):
            await knot.process(ssfile_path=path, vector_name="MISSING")
