"""``VitalSignsAggregator`` — per-patient summaries of vitals.

Operates over a tuple of ``(patient_id, vital_name, value, observed_at)``
rows. Returns a mapping ``patient_id -> {vital_name -> {mean, min, max,
latest}}``. Heavy aggregation is left to the production version.
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
        rows: Sequence[Mapping[str, Any]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(rows, (list, tuple)):
            raise TypeError(
                "VitalSignsAggregator: rows must be a list or tuple"
            )
        for row in rows:
            if not isinstance(row, Mapping):
                raise TypeError(
                    "VitalSignsAggregator: every row must be a Mapping"
                )
        self._rows = tuple(dict(r) for r in rows)
        super().__init__(_config=_config, **kwargs)

    async def process(
        self, **_: Any
    ) -> Mapping[str, Mapping[str, Mapping[str, float]]]:
        """Compute running mean, min, max, and latest per vital per patient and return the nested summary map.

        Returns:
            A nested mapping of patient_id -> vital_name -> {mean, min, max, latest} statistics.
        """
        out: dict[str, dict[str, dict[str, float]]] = {}
        for row in self._rows:
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
