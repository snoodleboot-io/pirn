"""``SubvolumeExtractor`` — crop a seismic volume to a sub-cube of interest."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class SubvolumeExtractor(Knot):
    """Extract a 3-D sub-cube from a parent volume."""

    def __init__(
        self,
        *,
        volume: Knot,
        inline_start: int,
        inline_end: int,
        xline_start: int,
        xline_end: int,
        sample_start: int,
        sample_end: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for label, value in (
            ("inline_start", inline_start),
            ("inline_end", inline_end),
            ("xline_start", xline_start),
            ("xline_end", xline_end),
            ("sample_start", sample_start),
            ("sample_end", sample_end),
        ):
            if not isinstance(value, int) or value < 0:
                raise ValueError(
                    f"SubvolumeExtractor: {label} must be a non-negative integer"
                )
        if inline_end <= inline_start:
            raise ValueError(
                "SubvolumeExtractor: inline_end must exceed inline_start"
            )
        if xline_end <= xline_start:
            raise ValueError(
                "SubvolumeExtractor: xline_end must exceed xline_start"
            )
        if sample_end <= sample_start:
            raise ValueError(
                "SubvolumeExtractor: sample_end must exceed sample_start"
            )
        self._inline_start = inline_start
        self._inline_end = inline_end
        self._xline_start = xline_start
        self._xline_end = xline_end
        self._sample_start = sample_start
        self._sample_end = sample_end
        super().__init__(volume=volume, _config=_config, **kwargs)

    async def process(self, volume: SegyVolume, **_: Any) -> SegyVolume:
        return SegyVolume(
            volume_id=f"{volume.volume_id}:sub",
            inline_count=self._inline_end - self._inline_start,
            xline_count=self._xline_end - self._xline_start,
            sample_count=self._sample_end - self._sample_start,
        )
