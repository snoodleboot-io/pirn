"""Unit tests for :class:`SegyHeaderParser`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_oilgas.seismic.segy_header_parser import SegyHeaderParser
from pirn_oilgas.types.parsed_trace_header import ParsedTraceHeader
from pirn_oilgas.types.segy_volume import SegyVolume

_VOLUME = SegyVolume(volume_id="v")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> SegyHeaderParser:
        return SegyHeaderParser(
            volume=None,  # type: ignore[arg-type]
            _config=KnotConfig(id="hp", validate_io=False),
        )

    async def test_returns_parsed_header(self) -> None:
        knot = self._make_knot()
        out = await knot.process(volume=_VOLUME)
        assert isinstance(out, ParsedTraceHeader)
