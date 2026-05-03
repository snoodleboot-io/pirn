"""``LabResultNormalizer`` — normalise lab values via a unit-conversion map.

Mapping is ``(from_unit, to_unit) -> multiplier``. A real deployment
would hook into UCUM-aware libraries (``pint``, ``ucum-py``); this
stub keeps the orchestration shape.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class LabResultNormalizer(Knot):
    """Normalise lab-result rows using a unit-conversion mapping."""

    def __init__(
        self,
        *,
        rows: Sequence[Mapping[str, Any]],
        unit_conversions: Mapping[tuple[str, str], float],
        target_unit: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(rows, (list, tuple)):
            raise TypeError("LabResultNormalizer: rows must be list/tuple")
        if not isinstance(unit_conversions, Mapping):
            raise TypeError(
                "LabResultNormalizer: unit_conversions must be a Mapping"
            )
        if not isinstance(target_unit, str):
            raise TypeError(
                "LabResultNormalizer: target_unit must be a string"
            )
        if not target_unit:
            raise ValueError(
                "LabResultNormalizer: target_unit must be non-empty"
            )
        self._rows = tuple(dict(r) for r in rows)
        self._conversions = dict(unit_conversions)
        self._target_unit = target_unit
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> tuple[Mapping[str, Any], ...]:
        """Convert each lab row's value to the target unit using the conversion map and return the normalised rows.

        Returns:
            A tuple of lab result row dicts with values converted to the target unit.
        """
        out: list[Mapping[str, Any]] = []
        for row in self._rows:
            from_unit = str(row.get("unit", ""))
            try:
                value = float(row.get("value", 0.0))
            except (TypeError, ValueError):
                value = 0.0
            multiplier = self._conversions.get(
                (from_unit, self._target_unit), 1.0
            )
            out.append(
                {
                    **row,
                    "value": value * multiplier,
                    "unit": self._target_unit,
                }
            )
        return tuple(out)
