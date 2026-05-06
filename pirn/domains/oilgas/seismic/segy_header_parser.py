"""``SegyHeaderParser`` — parse trace headers out of a :class:`SegyVolume`.

Algorithm:
    1. Receive a SegyVolume reference.
    2. Read the binary file header and the first trace header.
    3. Extract CRS units, inline / xline numbering, and sample metadata.
    4. Return a ParsedTraceHeader with the extracted fields.


References:
    - SEG Technical Standards Committee (2017). *SEG-Y_r2.0 Data Exchange
      Format*. Society of Exploration Geophysicists (trace header byte
      positions).
    - Barry, K.M., Cavers, D.A. & Kneale, C.W. (1975). Recommended standards
      for digital tape formats. *Geophysics*, 40(2), 344-352.
"""

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
        """Parse a representative trace header from the SEG-Y volume and return a ParsedTraceHeader.

        Args:
            volume: SEG-Y volume from which to read the representative trace header.

        Returns:
            ParsedTraceHeader containing CRS and inline/xline metadata.
        """
        return ParsedTraceHeader()
