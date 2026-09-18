"""``AnomalyDetector`` — screens a study for imaging anomalies.

Part of the ``examples.domain_formats.medical_triage_agent`` example.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot

from examples.domain_formats.medical_triage_agent.anomaly_report import AnomalyReport
from examples.domain_formats.medical_triage_agent.seeded_rng import SeededRng
from examples.domain_formats.medical_triage_agent.study import Study
from examples.domain_formats.medical_triage_agent.tissue_classification import (
    TissueClassification,
)


class AnomalyDetector(Knot):
    """Screens for imaging anomalies using statistical outlier detection.

    In production this would run a segmentation model against the pixel
    array and compare region statistics against modality-specific baselines.
    """

    _finding_pool: ClassVar[dict[str, tuple[str, ...]]] = {
        "lung": ("ground-glass opacity", "consolidation", "nodule (≥6mm)", "pleural effusion"),
        "bone": ("cortical irregularity", "focal lytic lesion", "sclerotic change"),
        "brain": ("focal hypodensity", "midline shift", "haemorrhagic change"),
        "soft_tissue": ("mass effect", "asymmetric density"),
        "cardiac": ("cardiomegaly", "pericardial effusion"),
        "liver": ("hepatic lesion", "biliary dilation"),
        "spine": ("compression fracture", "disc herniation"),
    }

    async def process(self, study: Study, tissue: TissueClassification, **_: Any) -> AnomalyReport:
        rng = SeededRng.for_study(study.study_id, "anomaly")
        pool = self._finding_pool.get(tissue.primary_tissue, ("incidental finding",))
        anomalies_found = rng.random() < 0.45
        if not anomalies_found:
            return AnomalyReport(
                study_id=study.study_id,
                anomalies_found=False,
                severity="none",
                findings=[],
                requires_urgent_review=False,
            )
        n_findings = rng.randint(1, min(3, len(pool)))
        findings = rng.sample(pool, k=n_findings)
        severity = rng.choice(["mild", "mild", "moderate", "severe"])
        urgent = severity == "severe" or (severity == "moderate" and rng.random() < 0.3)
        return AnomalyReport(
            study_id=study.study_id,
            anomalies_found=True,
            severity=severity,
            findings=findings,
            requires_urgent_review=urgent,
        )
