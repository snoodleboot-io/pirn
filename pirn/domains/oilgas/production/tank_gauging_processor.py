"""``TankGaugingProcessor`` — process tank gauge readings to compute net oil volume and BS&W."""

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
        tank_table: dict[str, float],
        bsw_correction_factor: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(tank_table, dict):
            raise TypeError("TankGaugingProcessor: tank_table must be a dict")
        if not isinstance(bsw_correction_factor, (int, float)):
            raise TypeError(
                "TankGaugingProcessor: bsw_correction_factor must be numeric"
            )
        if not (0.0 <= bsw_correction_factor <= 1.0):
            raise ValueError(
                "TankGaugingProcessor: bsw_correction_factor must be in [0, 1]"
            )
        self._tank_table = tank_table
        self._bsw_correction_factor = float(bsw_correction_factor)
        super().__init__(gauge_readings=gauge_readings, _config=_config, **kwargs)

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
                return table[float_to_key[lo]] + frac * (table[float_to_key[hi]] - table[float_to_key[lo]])
        return 0.0

    async def process(self, gauge_readings: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Compute gross volume, net oil, and BS&W-adjusted volume from gauge readings.

        Args:
            gauge_readings: Dict with ``opening_level_in``, ``closing_level_in``,
                ``bsw_pct``, and ``temperature_f``.

        Returns:
            Dict with ``gross_volume_bbl`` (float), ``net_oil_bbl`` (float),
            and ``bsw_adjusted_bbl`` (float).
        """
        if not isinstance(gauge_readings, dict):
            raise TypeError("TankGaugingProcessor: gauge_readings must be a dict")
        opening = float(gauge_readings.get("opening_level_in", 0.0))
        closing = float(gauge_readings.get("closing_level_in", 0.0))
        bsw_pct = float(gauge_readings.get("bsw_pct", 0.0))
        opening_vol = self._interpolate(self._tank_table, opening)
        closing_vol = self._interpolate(self._tank_table, closing)
        gross_volume = abs(closing_vol - opening_vol)
        bsw_fraction = bsw_pct / 100.0
        net_oil = gross_volume * (1.0 - bsw_fraction)
        bsw_adjusted = net_oil * (1.0 - self._bsw_correction_factor * bsw_fraction)
        return {
            "gross_volume_bbl": gross_volume,
            "net_oil_bbl": net_oil,
            "bsw_adjusted_bbl": bsw_adjusted,
        }
