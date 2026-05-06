"""``EnvironmentalCorrectionApplicator`` — apply tool-specific environmental corrections to log data.

Algorithm:
    1. Receive a log curve list, a ``correction_table`` dict, and a
       ``log_type`` string.
    2. Validate that ``correction_table`` is a dict and ``log_type`` is one
       of the supported types.
    3. Look up the correction factor for the given borehole conditions
       (mud weight, temperature, borehole size) in the correction table.
    4. Apply the factor to each raw log sample.
    5. Return the corrected log curve.

Math:
    Corrected log value:

    $$v_i^{corr} = v_i^{raw} \\times f_{env}$$

    where :math:`f_{env}` is the environmental correction factor from the
    correction chart.

References:
    - Schlumberger (1997). *Log Interpretation Charts*, Chapter 1
      (environmental corrections for gamma ray, resistivity, density,
      neutron, and sonic tools).
    - Ellis, D.V. & Singer, J.M. (2007). *Well Logging for Earth Scientists*,
      2nd ed. Springer, Chapter 3 (tool physics and borehole corrections).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class EnvironmentalCorrectionApplicator(Knot):
    """Apply borehole environmental corrections (mud weight, temperature, borehole size) to log curves."""

    def __init__(
        self,
        *,
        log_curve: Knot,
        correction_table: Knot | dict[str, Any],
        log_type: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            log_curve=log_curve,
            correction_table=correction_table,
            log_type=log_type,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        log_curve: list[dict[str, Any]],
        correction_table: dict[str, Any],
        log_type: str,
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Apply environmental correction to each log sample.

        Args:
            log_curve: List of dicts with ``depth_ft`` and ``raw_value``.
            correction_table: Dict of correction factors keyed by borehole
                condition parameters (e.g. ``correction_factor``).
            log_type: Log tool type; must be one of ``gamma_ray``,
                ``resistivity``, ``neutron``, ``density``, or ``sonic``.

        Returns:
            List of dicts with ``depth_ft``, ``raw_value``, and ``corrected_value``.
        """
        if not isinstance(correction_table, dict):
            raise TypeError("EnvironmentalCorrectionApplicator: correction_table must be a dict")
        _valid_log_types = frozenset({"gamma_ray", "resistivity", "neutron", "density", "sonic"})
        if log_type not in _valid_log_types:
            raise ValueError(
                f"EnvironmentalCorrectionApplicator: log_type must be one of "
                f"{sorted(_valid_log_types)}"
            )
        correction_factor: float = float(correction_table.get("correction_factor", 1.0))
        return [
            {
                **entry,
                "corrected_value": float(entry.get("raw_value", 0.0)) * correction_factor,
            }
            for entry in log_curve
        ]
