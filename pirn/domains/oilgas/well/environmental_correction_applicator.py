"""``EnvironmentalCorrectionApplicator`` — apply tool-specific environmental corrections to log data."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class EnvironmentalCorrectionApplicator(Knot):
    """Apply borehole environmental corrections (mud weight, temperature, borehole size) to log curves."""

    valid_log_types: ClassVar[frozenset[str]] = frozenset(
        {"gamma_ray", "resistivity", "neutron", "density", "sonic"}
    )

    def __init__(
        self,
        *,
        log_curve: Knot,
        correction_table: dict[str, Any],
        log_type: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(correction_table, dict):
            raise TypeError(
                "EnvironmentalCorrectionApplicator: correction_table must be a dict"
            )
        if log_type not in self.valid_log_types:
            raise ValueError(
                f"EnvironmentalCorrectionApplicator: log_type must be one of "
                f"{sorted(self.valid_log_types)}"
            )
        self._correction_table = correction_table
        self._log_type = log_type
        super().__init__(log_curve=log_curve, _config=_config, **kwargs)

    async def process(
        self, log_curve: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Apply environmental correction to each log sample.

        Args:
            log_curve: List of dicts with ``depth_ft`` and ``raw_value``.

        Returns:
            List of dicts with ``depth_ft``, ``raw_value``, and ``corrected_value``.
        """
        correction_factor: float = float(
            self._correction_table.get("correction_factor", 1.0)
        )
        return [
            {
                **entry,
                "corrected_value": float(entry.get("raw_value", 0.0)) * correction_factor,
            }
            for entry in log_curve
        ]
