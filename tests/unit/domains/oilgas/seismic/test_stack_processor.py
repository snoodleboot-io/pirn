"""Unit tests for :class:`StackProcessor`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.stack_processor import StackProcessor
from pirn.domains.oilgas.types.segy_volume import SegyVolume

_GATHER = SegyVolume(volume_id="vol")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> StackProcessor:
        return StackProcessor(
            gather=None,  # type: ignore[arg-type]
            _config=KnotConfig(id="st", validate_io=False),
        )

    async def test_returns_stacked_volume(self) -> None:
        knot = self._make_knot()
        out = await knot.process(gather=_GATHER)
        assert isinstance(out, SegyVolume)
        assert out.volume_id.endswith(":stacked")
