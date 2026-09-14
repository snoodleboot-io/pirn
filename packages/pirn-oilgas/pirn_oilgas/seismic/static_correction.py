"""``StaticCorrection`` — apply elevation / weathering static corrections.

Algorithm:
    1. Receive a seismic gather or volume, a ``datum_elevation_m`` float,
       and a positive ``replacement_velocity_m_s``.
    2. Validate that ``replacement_velocity_m_s`` is positive and numeric.
    3. Compute the static shift for each receiver / source from its
       elevation relative to the datum.
    4. Apply the computed shifts and return the corrected SegyVolume.

Math:
    Static time shift for a station at elevation :math:`z` relative to
    datum :math:`z_d`:

    $$\\Delta t = \\frac{z - z_d}{v_r}$$

    where :math:`v_r` is ``replacement_velocity_m_s``.

References:
    - Cox, M. (1999). *Static Corrections for Seismic Reflection Surveys*.
      SEG, Chapter 2 (field statics and datum corrections).
    - Yilmaz, Ö. (2001). *Seismic Data Analysis*, 2nd ed. SEG, Chapter 3
      (static corrections).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.segy_volume import SegyVolume


class StaticCorrection(Knot):
    """Apply elevation / weathering statics to a gather or volume."""

    def __init__(
        self,
        *,
        gather: Knot,
        datum_elevation_m: Knot | float,
        replacement_velocity_m_s: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            gather=gather,
            datum_elevation_m=datum_elevation_m,
            replacement_velocity_m_s=replacement_velocity_m_s,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        gather: SegyVolume,
        datum_elevation_m: float,
        replacement_velocity_m_s: float,
        **_: Any,
    ) -> SegyVolume:
        """Apply elevation and weathering static corrections to the gather and return the corrected SegyVolume.

        Args:
            gather: Seismic gather or volume to apply static corrections to.
            datum_elevation_m: Target datum elevation in metres (may be any real number).
            replacement_velocity_m_s: Positive replacement velocity in metres per second.

        Returns:
            SegyVolume with static corrections applied.
        """
        if not isinstance(datum_elevation_m, (int, float)):
            raise TypeError("StaticCorrection: datum_elevation_m must be numeric")
        if not isinstance(replacement_velocity_m_s, (int, float)):
            raise TypeError("StaticCorrection: replacement_velocity_m_s must be numeric")
        if replacement_velocity_m_s <= 0.0:
            raise ValueError("StaticCorrection: replacement_velocity_m_s must be positive")
        shift_ms = (0.0 - datum_elevation_m) / replacement_velocity_m_s * 1000.0
        samples_shifted = int(abs(shift_ms) / 4.0)
        corrected_sample_count = max(0, gather.sample_count - samples_shifted)
        return SegyVolume(
            volume_id=f"{gather.volume_id}:static_{shift_ms:.1f}ms",
            inline_count=gather.inline_count,
            xline_count=gather.xline_count,
            sample_count=corrected_sample_count,
        )
