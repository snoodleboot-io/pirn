"""Unit tests for :class:`EclipseSmspecParser`."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.reservoir.eclipse_smspec_parser import EclipseSmspecParser
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


def _write_smspec(path: Path, keywords: list[str], wgnames: list[str], n_steps: int) -> None:
    """Write a minimal valid Eclipse SMSPEC binary using resfo."""
    import numpy as np
    import resfo

    n = len(keywords)
    records = [
        ("INTEHEAD", np.array([100, 1], dtype=np.int32)),
        ("DIMENS  ", np.array([n, 1, n_steps], dtype=np.int32)),
        ("KEYWORDS", np.array([kw.ljust(8) for kw in keywords])),
        ("WGNAMES ", np.array([wg.ljust(8) for wg in wgnames])),
        ("UNITS   ", np.array(["SM3/DAY ".ljust(8)] * n)),
    ]
    resfo.write(str(path), records)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(
        self,
        smspec_path: str = "/x.smspec",
        vector_name: str = "WOPR:WELL1",
    ) -> EclipseSmspecParser:
        return EclipseSmspecParser(
            smspec_path=smspec_path,
            vector_name=vector_name,
            _config=KnotConfig(id="ep"),
        )

    async def test_rejects_empty_smspec_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "smspec_path"):
            await knot.process(smspec_path="", vector_name="WOPR:WELL1")

    async def test_rejects_empty_vector_name(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "vector_name"):
            await knot.process(smspec_path="/x.smspec", vector_name="")

    async def test_raises_file_not_found(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(FileNotFoundError):
            await knot.process(smspec_path="/nonexistent.smspec", vector_name="WOPR:W1")

    async def test_returns_series(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            smspec = Path(td) / "test.smspec"
            _write_smspec(smspec, ["WOPR"], ["W1"], n_steps=30)
            knot = self._make_knot(smspec_path=str(smspec), vector_name="WOPR:W1")
            out = await knot.process(smspec_path=str(smspec), vector_name="WOPR:W1")
        assert isinstance(out, ScadaTimeSeries)
        assert out.sensor_id == "eclipse:WOPR:W1"
        assert out.sample_count == 30
        assert out.sample_interval_sec == 86400.0

    async def test_raises_on_missing_vector(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            smspec = Path(td) / "test.smspec"
            _write_smspec(smspec, ["WOPR"], ["W1"], n_steps=10)
            knot = self._make_knot(smspec_path=str(smspec), vector_name="FOPT")
            with self.assertRaises(KeyError):
                await knot.process(smspec_path=str(smspec), vector_name="FOPT")
