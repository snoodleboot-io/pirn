"""``LabResultNormalizer`` — normalise lab values via a unit-conversion map.

Mapping is ``(from_unit, to_unit) -> multiplier``. A real deployment
would hook into UCUM-aware libraries (``pint``, ``ucum-py``); this
stub keeps the orchestration shape.

Algorithm:
    1. Receive rows, unit_conversions mapping, and target_unit string.
    2. Validate types: rows is list/tuple, unit_conversions is Mapping, target_unit is non-empty string.
    3. For each row, look up (from_unit, target_unit) in conversions (default multiplier 1.0).
    4. Multiply the row value by the multiplier and set unit to target_unit.
    5. Return the normalised rows as a tuple.

Math:
    $$v_{\\text{norm}} = v_{\\text{orig}} \\times m_{(u_{\\text{from}},\\, u_{\\text{to}})}$$

References:
    - UCUM: https://ucum.org/
    - LOINC: https://loinc.org/
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
        rows: Knot | Sequence[Mapping[str, Any]],
        unit_conversions: Knot | Mapping[tuple[str, str], float],
        target_unit: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            unit_conversions=unit_conversions,
            target_unit=target_unit,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        rows: Sequence[Mapping[str, Any]],
        unit_conversions: Mapping[tuple[str, str], float],
        target_unit: str,
        **_: Any,
    ) -> tuple[Mapping[str, Any], ...]:
        """Convert each lab row's value to the target unit using the conversion map and return the normalised rows.

        Args:
            rows: Sequence of lab result row dicts with 'unit' and 'value' keys.
            unit_conversions: Mapping of (from_unit, to_unit) pairs to multipliers.
            target_unit: Non-empty string identifying the desired output unit.

        Returns:
            A tuple of lab result row dicts with values converted to the target unit.

        Raises:
            TypeError: If rows is not a list/tuple, unit_conversions is not a Mapping, or target_unit is not a string.
            ValueError: If target_unit is empty.
        """
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
        out: list[Mapping[str, Any]] = []
        for row in rows:
            from_unit = str(row.get("unit", ""))
            try:
                value = float(row.get("value", 0.0))
            except (TypeError, ValueError):
                value = 0.0
            multiplier = unit_conversions.get(
                (from_unit, target_unit), 1.0
            )
            out.append(
                {
                    **row,
                    "value": value * multiplier,
                    "unit": target_unit,
                }
            )
        return tuple(out)
