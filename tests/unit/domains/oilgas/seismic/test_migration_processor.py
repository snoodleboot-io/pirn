"""Unit tests for :class:`MigrationProcessor`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.migration_processor import MigrationProcessor
from pirn.domains.oilgas.types.segy_volume import SegyVolume

_VOLUME = SegyVolume(volume_id="vol")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, method: str = "kirchhoff") -> MigrationProcessor:
        return MigrationProcessor(
            volume=None,  # type: ignore[arg-type]
            method=method,
            _config=KnotConfig(id="mig", validate_io=False),
        )

    async def test_rejects_invalid_method(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "method"):
            await knot.process(volume=_VOLUME, method="not_a_method")

    async def test_returns_migrated_volume(self) -> None:
        knot = self._make_knot()
        out = await knot.process(volume=_VOLUME, method="kirchhoff")
        assert isinstance(out, SegyVolume)
        assert "migrated_kirchhoff" in out.volume_id

    async def test_accepts_all_valid_methods(self) -> None:
        for method in ("kirchhoff", "rtm", "phase_shift", "stolt"):
            knot = self._make_knot(method=method)
            out = await knot.process(volume=_VOLUME, method=method)
            assert isinstance(out, SegyVolume)
