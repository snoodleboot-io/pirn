"""``TankGaugingProcessor`` — process tank gauge readings to compute net oil volume and BS&W.

Algorithm:
    1. Receive a gauge readings dict, a ``tank_table`` (level→volume lookup),
       and a ``bsw_correction_factor`` in [0, 1].
    2. Validate that ``tank_table`` is a dict and ``bsw_correction_factor`` is in [0, 1].
    3. Interpolate tank volumes at the opening and closing gauge levels.
    4. Compute gross volume = |closing_vol - opening_vol|.
    5. Apply BS&W fraction and correction factor to derive net oil and adjusted volumes.
    6. Return gross, net oil, and BS&W-adjusted volumes.

Math:
    Net oil volume:

    $$V_{\\text{net}} = V_{\\text{gross}} \\times (1 - f_{\\text{BSW}})$$

    BS&W-adjusted volume:

    $$V_{\\text{adj}} = V_{\\text{net}} \\times (1 - k \\cdot f_{\\text{BSW}})$$

    where :math:`f_{\\text{BSW}} = \\text{bsw\\_pct} / 100` and :math:`k` is
    the BS&W correction factor.

References:
    - API MPMS Chapter 3.1A — Standard Practice for the Manual Gauging of
      Petroleum and Petroleum Products.
    - API MPMS Chapter 17.1 — Guidelines for Marine Cargo Inspection (BS&W
      correction methodology).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class TankGaugingProcessor(Knot):
    """Compute gross volume, net oil, and BS&W-adjusted volume from tank gauge readings."""

    def __init__(
        self,
        *,
        gauge_readings: Knot,
        tank_table: Knot,
        bsw_correction_factor: Knot | float,
        opening_field: Knot | str = "opening_level_in",
        closing_field: Knot | str = "closing_level_in",
        bsw_pct_field: Knot | str = "bsw_pct",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            gauge_readings=gauge_readings,
            tank_table=tank_table,
            bsw_correction_factor=bsw_correction_factor,
            opening_field=opening_field,
            closing_field=closing_field,
            bsw_pct_field=bsw_pct_field,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _interpolate(table: dict[str, float], level: float) -> float:
        if not table:
            return 0.0
        float_to_key = {float(k): k for k in table}
        keys = sorted(float_to_key)
        if level <= keys[0]:
            return table[float_to_key[keys[0]]]
        if level >= keys[-1]:
            return table[float_to_key[keys[-1]]]
        for i in range(len(keys) - 1):
            lo, hi = keys[i], keys[i + 1]
            if lo <= level <= hi:
                frac = (level - lo) / (hi - lo)
                return table[float_to_key[lo]] + frac * (
                    table[float_to_key[hi]] - table[float_to_key[lo]]
                )
        return 0.0

    async def process(
        self,
        gauge_readings: dict[str, Any],
        tank_table: dict[str, float],
        bsw_correction_factor: float,
        opening_field: str = "opening_level_in",
        closing_field: str = "closing_level_in",
        bsw_pct_field: str = "bsw_pct",
        **_: Any,
    ) -> dict[str, Any]:
        """Compute gross volume, net oil, and BS&W-adjusted volume from gauge readings.

        Args:
            gauge_readings: Dict with tank gauge readings.
            tank_table: Dict mapping gauge level (str key, float-convertible) to
                volume in barrels.
            bsw_correction_factor: BS&W correction factor in [0, 1].
            opening_field: Tag name for opening gauge level (inches) in gauge_readings.
            closing_field: Tag name for closing gauge level (inches) in gauge_readings.
            bsw_pct_field: Tag name for BS&W percentage in gauge_readings.

        Returns:
            Dict with ``gross_volume_bbl`` (float), ``net_oil_bbl`` (float),
            and ``bsw_adjusted_bbl`` (float).

        Raises:
            KeyError: If gauge_readings is missing any required field.
        """
        if not isinstance(tank_table, dict):
            raise TypeError("TankGaugingProcessor: tank_table must be a dict")
        if not isinstance(bsw_correction_factor, (int, float)):
            raise TypeError("TankGaugingProcessor: bsw_correction_factor must be numeric")
        if not (0.0 <= bsw_correction_factor <= 1.0):
            raise ValueError("TankGaugingProcessor: bsw_correction_factor must be in [0, 1]")
        if not isinstance(gauge_readings, dict):
            raise TypeError("TankGaugingProcessor: gauge_readings must be a dict")
        for field in (opening_field, closing_field, bsw_pct_field):
            if field not in gauge_readings:
                raise KeyError(
                    f"TankGaugingProcessor: gauge_readings missing required field '{field}'; "
                    f"got: {list(gauge_readings)}"
                )
        opening = float(gauge_readings[opening_field])
        closing = float(gauge_readings[closing_field])
        bsw_pct = float(gauge_readings[bsw_pct_field])
        opening_vol = self._interpolate(tank_table, opening)
        closing_vol = self._interpolate(tank_table, closing)
        gross_volume = abs(closing_vol - opening_vol)
        bsw_fraction = bsw_pct / 100.0
        net_oil = gross_volume * (1.0 - bsw_fraction)
        bsw_adjusted = net_oil * (1.0 - float(bsw_correction_factor) * bsw_fraction)
        return {
            "gross_volume_bbl": gross_volume,
            "net_oil_bbl": net_oil,
            "bsw_adjusted_bbl": bsw_adjusted,
        }
