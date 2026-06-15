"""``SubvolumeExtractor`` — crop a seismic volume to a sub-cube of interest.

Algorithm:
    1. Receive a parent SegyVolume and six non-negative integer bounds:
       ``inline_start``, ``inline_end``, ``xline_start``, ``xline_end``,
       ``sample_start``, ``sample_end``.
    2. Validate that all bounds are non-negative integers and that each
       end exceeds its corresponding start.
    3. Crop the parent volume to the specified inline, xline, and sample
       ranges.
    4. Return a SegyVolume reference for the extracted sub-cube.


References:
    - Liner, C.L. (2004). *Elements of 3D Seismology*, 2nd ed. PennWell,
      Chapter 2 (3-D survey geometry and sub-volume extraction).
    - Brown, A.R. (2011). *Interpretation of Three-Dimensional Seismic Data*,
      7th ed. SEG/AAPG Memoir 42, Chapter 2 (3-D data volumes).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.segy_volume import SegyVolume


class SubvolumeExtractor(Knot):
    """Extract a 3-D sub-cube from a parent volume."""

    def __init__(
        self,
        *,
        volume: Knot,
        inline_start: Knot | int,
        inline_end: Knot | int,
        xline_start: Knot | int,
        xline_end: Knot | int,
        sample_start: Knot | int,
        sample_end: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            volume=volume,
            inline_start=inline_start,
            inline_end=inline_end,
            xline_start=xline_start,
            xline_end=xline_end,
            sample_start=sample_start,
            sample_end=sample_end,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        volume: SegyVolume,
        inline_start: int,
        inline_end: int,
        xline_start: int,
        xline_end: int,
        sample_start: int,
        sample_end: int,
        **_: Any,
    ) -> SegyVolume:
        """Crop the input volume to the configured inline, xline, and sample bounds and return the sub-volume.

        Args:
            volume: 3-D seismic volume to crop.
            inline_start: Non-negative start inline index (inclusive).
            inline_end: Non-negative end inline index (exclusive); must exceed ``inline_start``.
            xline_start: Non-negative start crossline index (inclusive).
            xline_end: Non-negative end crossline index (exclusive); must exceed ``xline_start``.
            sample_start: Non-negative start sample index (inclusive).
            sample_end: Non-negative end sample index (exclusive); must exceed ``sample_start``.

        Returns:
            SegyVolume trimmed to the configured inline, xline, and sample ranges.
        """
        for label, value in (
            ("inline_start", inline_start),
            ("inline_end", inline_end),
            ("xline_start", xline_start),
            ("xline_end", xline_end),
            ("sample_start", sample_start),
            ("sample_end", sample_end),
        ):
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"SubvolumeExtractor: {label} must be a non-negative integer")
        if inline_end <= inline_start:
            raise ValueError("SubvolumeExtractor: inline_end must exceed inline_start")
        if xline_end <= xline_start:
            raise ValueError("SubvolumeExtractor: xline_end must exceed xline_start")
        if sample_end <= sample_start:
            raise ValueError("SubvolumeExtractor: sample_end must exceed sample_start")
        return SegyVolume(
            volume_id=f"{volume.volume_id}:sub",
            inline_count=inline_end - inline_start,
            xline_count=xline_end - xline_start,
            sample_count=sample_end - sample_start,
        )
