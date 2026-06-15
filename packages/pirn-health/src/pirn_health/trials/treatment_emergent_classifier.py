"""``TreatmentEmergentClassifier`` — flag treatment-emergent adverse events.

A treatment-emergent adverse event (TEAE) is any AE that begins at or
after a subject's first treatment exposure. Production deployments
respect end-of-treatment + safety-follow-up windows; this stub uses
the ``observed_at >= first_exposure`` rule.

Algorithm:
    1. For each adverse-event record, look up the subject's first exposure date.
    2. Mark the event as treatment-emergent if observed_at >= first_exposure.
    3. Return the annotated event sequence.

Math:
    Treatment-emergent indicator:

    $$\\text{TE}(r) = \\mathbf{1}[t_{\\text{obs}} \\geq t_{\\text{exp}}]$$

    where $t_{\\text{obs}}$ is the event date and $t_{\\text{exp}}$ is the first exposure date.

References:
    - ICH E3. (1995). Structure and Content of Clinical Study Reports. Section 12.3.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.types.clinical_trial_record import ClinicalTrialRecord


class TreatmentEmergentClassifier(Knot):
    """Annotate adverse-event records with a treatment-emergent flag."""

    def __init__(
        self,
        *,
        events: Knot | Sequence[ClinicalTrialRecord],
        exposures: Knot | Mapping[str, datetime],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(events=events, exposures=exposures, _config=_config, **kwargs)

    async def process(
        self,
        events: Sequence[ClinicalTrialRecord],
        exposures: Mapping[str, datetime],
        **_: Any,
    ) -> Sequence[Mapping[str, Any]]:
        """Flag each adverse event as treatment-emergent based on the subject's first exposure date.

        Args:
            events: Sequence of adverse-event ClinicalTrialRecord objects.
            exposures: Mapping of subject_id to first treatment-exposure datetime.

        Returns:
            Sequence of dicts with trial_id, subject_id, treatment_emergent flag,
            and observed_at ISO timestamp.
        """
        annotated: list[Mapping[str, Any]] = []
        for event in events:
            first_exposure = exposures.get(event.subject_id)
            is_emergent = first_exposure is not None and event.observed_at >= first_exposure
            annotated.append(
                {
                    "trial_id": event.trial_id,
                    "subject_id": event.subject_id,
                    "treatment_emergent": is_emergent,
                    "observed_at": event.observed_at.isoformat(),
                }
            )
        return tuple(annotated)
