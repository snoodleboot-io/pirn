"""``TissueClassifier`` — names the primary tissue visible in a study.

Part of the ``examples.domain_formats.medical_triage_agent`` example.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot

from examples.domain_formats.medical_triage_agent.seeded_rng import SeededRng
from examples.domain_formats.medical_triage_agent.study import Study
from examples.domain_formats.medical_triage_agent.tissue_classification import (
    TissueClassification,
)


class TissueClassifier(Knot):
    """Classifies the primary tissue type from modality and pixel statistics.

    A real implementation would pass the normalised pixel array through a
    lightweight CNN or histogram-based classifier.
    """

    _modality_tissues: ClassVar[dict[str, tuple[str, ...]]] = {
        "CT": ("lung", "bone", "soft_tissue", "liver", "brain"),
        "MRI": ("brain", "soft_tissue", "cardiac", "spine"),
        "XR": ("bone", "lung", "soft_tissue"),
        "US": ("cardiac", "soft_tissue", "liver"),
    }

    async def process(self, study: Study, **_: Any) -> TissueClassification:
        rng = SeededRng.for_study(study.study_id, "tissue")
        candidates = self._modality_tissues.get(study.modality, ("soft_tissue",))
        primary = rng.choice(candidates)
        confidence = rng.uniform(0.55, 0.97)
        secondary = rng.sample(
            [t for t in candidates if t != primary],
            k=min(2, len(candidates) - 1),
        )
        return TissueClassification(
            study_id=study.study_id,
            primary_tissue=primary,
            confidence=round(confidence, 3),
            secondary_findings=secondary,
        )
