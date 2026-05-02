"""``SegyHeaderParser`` — parse trace headers out of a :class:`SegyVolume`."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.parsed_trace_header import ParsedTraceHeader
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class SegyHeaderParser(Knot):
    """Parse a single representative trace header from the volume.

    Real implementations stream every header; the stub returns the
    representative header so downstream knots can reason about CRS units
    and inline / xline numbering during orchestration tests.
    """

    def __init__(
        self,
        *,
        volume: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(volume=volume, _config=_config, **kwargs)

    async def process(self, volume: SegyVolume, **_: Any) -> ParsedTraceHeader:
        return ParsedTraceHeader()
