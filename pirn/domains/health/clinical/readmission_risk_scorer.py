"""``ReadmissionRiskScorer`` — stub readmission-risk model.

Production deployments would call a trained classifier (sklearn,
XGBoost, deep model) loaded from the model registry. This stub emits
a deterministic score derived from a small heuristic so the
orchestration plumbing can be exercised without a real model.

Algorithm:
    1. Receive a sequence of ClinicalRecords.
    2. Validate that records is a list/tuple of ClinicalRecords.
    3. For each record, compute a heuristic score from the observation_code count.
    4. Track the maximum score per patient_id across multiple records.
    5. Return a mapping of patient_id to readmission risk score.

Math:
    $$\\text{score}(r) = \\min\\!\\left(1.0,\\, \\frac{|r.\\text{observation\\_codes}|}{10}\\right)$$

References:
    - LACE Index: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2845681/
    - HL7 FHIR R4 RiskAssessment: https://hl7.org/fhir/R4/riskassessment.html
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
        records: Knot | Sequence[ClinicalRecord],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(records=records, _config=_config, **kwargs)

    async def process(
        self,
        records: Sequence[ClinicalRecord],
        **_: Any,
    ) -> Mapping[str, float]:
        """Score each patient's readmission risk from observation code count and return a patient_id-to-score map.

        Args:
            records: Sequence of ClinicalRecords to score.

        Returns:
            A mapping from patient_id to a readmission risk score in [0.0, 1.0].

        Raises:
            TypeError: If records is not a list/tuple or contains non-ClinicalRecord items.
        """
        if not isinstance(records, (list, tuple)):
            raise TypeError(
                "ReadmissionRiskScorer: records must be a list or tuple"
            )
        for record in records:
            if not isinstance(record, ClinicalRecord):
                raise TypeError(
                    "ReadmissionRiskScorer: every record must be a ClinicalRecord"
                )
        out: dict[str, float] = {}
        for record in records:
            # Stub deterministic score — count of observation codes saturated.
            n_codes = len(record.observation_codes)
            score = min(1.0, n_codes / 10.0)
            existing = out.get(record.patient_id, 0.0)
            out[record.patient_id] = max(existing, score)
        return out
