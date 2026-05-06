"""``VitalSignsAggregator`` — per-patient summaries of vitals.

Operates over a tuple of ``(patient_id, vital_name, value, observed_at)``
rows. Returns a mapping ``patient_id -> {vital_name -> {mean, min, max,
latest}}``. Heavy aggregation is left to the production version.

Algorithm:
    1. Receive a sequence of vital sign row dicts.
    2. Validate that rows is a list/tuple of Mappings.
    3. For each row, group by patient_id and vital_name.
    4. Compute running mean, min, max, latest, and count per bucket.
    5. Return the nested summary mapping.

Math:
    $$\\bar{v}_{n} = \\frac{\\bar{v}_{n-1} \\cdot (n-1) + v_n}{n}$$

References:
    - HL7 FHIR R4 Observation: https://hl7.org/fhir/R4/observation.html
    - LOINC vital signs panel: https://loinc.org/85353-1/
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class VitalSignsAggregator(Knot):
    """Compute per-patient vital-sign summaries."""

    def __init__(
        self,
        *,
        rows: Knot | Sequence[Mapping[str, Any]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(rows=rows, _config=_config, **kwargs)

    async def process(
        self,
        rows: Sequence[Mapping[str, Any]],
        **_: Any,
    ) -> Mapping[str, Mapping[str, Mapping[str, float]]]:
        """Compute running mean, min, max, and latest per vital per patient and return the nested summary map.

        Args:
            rows: Sequence of vital sign row dicts with 'patient_id', 'vital_name', and 'value' keys.

        Returns:
            A nested mapping of patient_id -> vital_name -> {mean, min, max, latest} statistics.

        Raises:
            TypeError: If rows is not a list/tuple or contains non-Mapping items.
        """
        if not isinstance(rows, (list, tuple)):
            raise TypeError(
                "VitalSignsAggregator: rows must be a list or tuple"
            )
        for row in rows:
            if not isinstance(row, Mapping):
                raise TypeError(
                    "VitalSignsAggregator: every row must be a Mapping"
                )
        out: dict[str, dict[str, dict[str, float]]] = {}
        for row in rows:
            patient_id = str(row.get("patient_id", ""))
            vital_name = str(row.get("vital_name", ""))
            try:
                value = float(row.get("value", 0.0))
            except (TypeError, ValueError):
                value = 0.0
            patient_bucket = out.setdefault(patient_id, {})
            current = patient_bucket.get(vital_name)
            if current is None:
                patient_bucket[vital_name] = {
                    "mean": value,
                    "min": value,
                    "max": value,
                    "latest": value,
                    "count": 1.0,
                }
            else:
                count = current["count"] + 1.0
                current["mean"] = (
                    current["mean"] * current["count"] + value
                ) / count
                current["min"] = min(current["min"], value)
                current["max"] = max(current["max"], value)
                current["latest"] = value
                current["count"] = count
        return out
