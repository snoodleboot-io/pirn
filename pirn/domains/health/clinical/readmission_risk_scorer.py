"""``ReadmissionRiskScorer`` — stub readmission-risk model.

Production deployments would call a trained classifier (sklearn,
XGBoost, deep model) loaded from the model registry. This stub emits
a deterministic score derived from a small heuristic so the
orchestration plumbing can be exercised without a real model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.clinical_record import ClinicalRecord


class ReadmissionRiskScorer(Knot):
    """Emit a readmission-risk score in [0, 1] per patient."""

    def __init__(
        self,
        *,
        records: Sequence[ClinicalRecord],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(records, (list, tuple)):
            raise TypeError(
                "ReadmissionRiskScorer: records must be a list or tuple"
            )
        for record in records:
            if not isinstance(record, ClinicalRecord):
                raise TypeError(
                    "ReadmissionRiskScorer: every record must be a ClinicalRecord"
                )
        self._records = tuple(records)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, float]:
        out: dict[str, float] = {}
        for record in self._records:
            # Stub deterministic score — count of observation codes saturated.
            n_codes = len(record.observation_codes)
            score = min(1.0, n_codes / 10.0)
            existing = out.get(record.patient_id, 0.0)
            out[record.patient_id] = max(existing, score)
        return out
