"""Unit tests for :class:`FrequencyDecomposer`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.frequency_decomposer import FrequencyDecomposer
from pirn.domains.oilgas.types.segy_volume import SegyVolume

_VOLUME = SegyVolume(volume_id="vol")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> FrequencyDecomposer:
        return FrequencyDecomposer(
            volume=None,  # type: ignore[arg-type]
            center_frequencies_hz=(10.0, 30.0, 60.0),
            _config=KnotConfig(id="fd", validate_io=False),
        )

    async def test_rejects_empty_frequencies(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(volume=_VOLUME, center_frequencies_hz=())

    async def test_rejects_non_positive_frequency(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "positive"):
            await knot.process(volume=_VOLUME, center_frequencies_hz=(10.0, -5.0))

    async def test_returns_volume_per_band(self) -> None:
        knot = self._make_knot()
        out = await knot.process(volume=_VOLUME, center_frequencies_hz=(10.0, 30.0, 60.0))
        assert isinstance(out, tuple)
        assert len(out) == 3
        for v in out:
            assert isinstance(v, SegyVolume)
