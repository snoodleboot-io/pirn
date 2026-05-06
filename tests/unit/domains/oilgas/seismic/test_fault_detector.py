"""Unit tests for :class:`FaultDetector`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.fault_detector import FaultDetector
from pirn.domains.oilgas.types.segy_volume import SegyVolume

_VOLUME = SegyVolume(volume_id="vol")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> FaultDetector:
        return FaultDetector(
            attribute_volume=None,  # type: ignore[arg-type]
            coherence_threshold=0.5,
            _config=KnotConfig(id="fd", validate_io=False),
        )

    async def test_rejects_non_numeric_threshold(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "coherence_threshold"):
            await knot.process(attribute_volume=_VOLUME, coherence_threshold="x")  # type: ignore[arg-type]

    async def test_rejects_out_of_range_threshold(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, r"\[0, 1\]"):
            await knot.process(attribute_volume=_VOLUME, coherence_threshold=2.0)

    async def test_returns_fault_volume(self) -> None:
        knot = self._make_knot()
        out = await knot.process(attribute_volume=_VOLUME, coherence_threshold=0.5)
        assert isinstance(out, SegyVolume)
        assert out.volume_id.endswith(":faults")
