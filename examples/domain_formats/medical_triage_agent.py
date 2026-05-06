"""Medical imaging triage agent — dynamic DAG over a DICOM study queue.

Processes a queue of DICOM studies through a multi-step analysis loop.
Each study is dispatched to three concurrent analysis knots (windowing,
tissue classification, anomaly detection), results are aggregated, and a
triage decision either routes the next study or terminates the run.

Pipeline shape (one iteration per study):

    StudyDispatcher ──► WindowingAnalyser   ──┐
                    ──► TissueClassifier    ──┼──► FindingsAggregator ──► TriageDecider
                    ──► AnomalyDetector     ──┘

    TriageDecider:
        → next StudyDispatcher(queue=self)   (more studies remain)
        → _TriageReport(queue=self)          (queue exhausted)

Working with real DICOM data:

    Replace ``_synthetic_study()`` with bytes decoded by ``DicomFormat``:

        from pirn.domains.connectors.file_formats.dicom_format import DicomFormat

        fmt = DicomFormat()
        records = await fmt.decode(dicom_bytes)   # one record per DICOM file

    The record schema each knot expects matches DicomFormat output exactly:
        patient_id, modality, study_date, series_number,
        rows, columns, pixel_data (float32 bytes), metadata.

Run with:
    uv run python examples/domain_formats/medical_triage_agent.py
"""

from __future__ import annotations

import asyncio
import hashlib
import random
import struct
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.aggregator import Aggregator
from pirn.tapestry import Tapestry, get_current_store

TRIAGE_COMPLETE_ID = "triage_complete"

# ----------------------------------------------------------------- data models


@dataclass(frozen=True)
class DicomRecord:
    """Matches the record schema emitted by ``DicomFormat.decode()``."""

    patient_id: str
    modality: str
    study_date: str
    series_number: int
    rows: int
    columns: int
    pixel_data: bytes
    metadata: dict[str, str]


@dataclass(frozen=True)
class Study:
    study_id: str
    records: tuple[DicomRecord, ...]

    @property
    def modality(self) -> str:
        return self.records[0].modality if self.records else "UNKNOWN"

    @property
    def n_pixels(self) -> int:
        return sum(len(r.pixel_data) // 4 for r in self.records)


@dataclass(frozen=True)
class WindowingResult:
    study_id: str
    window_level: float
    window_width: float
    clipped_fraction: float


@dataclass(frozen=True)
class TissueClassification:
    study_id: str
    primary_tissue: str
    confidence: float
    secondary_findings: list[str]


@dataclass(frozen=True)
class AnomalyReport:
    study_id: str
    anomalies_found: bool
    severity: str
    findings: list[str]
    requires_urgent_review: bool


@dataclass(frozen=True)
class TriageOutcome:
    study_id: str
    decision: str
    windowing: WindowingResult
    tissue: TissueClassification
    anomalies: AnomalyReport
    rationale: str


@dataclass(frozen=True)
class TriageQueue:
    studies: tuple[Study, ...]
    study_idx: int = 0
    outcomes: tuple[TriageOutcome, ...] = ()

    @property
    def current_study(self) -> Study:
        return self.studies[self.study_idx]

    @property
    def done(self) -> bool:
        return self.study_idx >= len(self.studies)

    def evolve(self, **changes: Any) -> TriageQueue:
        return replace(self, **changes)


# ----------------------------------------------------------------- synthetic data


def _rng(study_id: str, extra: str = "") -> random.Random:
    key = f"{study_id}|{extra}"
    seed = int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def _synthetic_pixel_data(rows: int, cols: int, rng: random.Random) -> bytes:
    n = rows * cols
    values = [rng.gauss(0.0, 400.0) for _ in range(n)]
    return struct.pack(f">{n}f", *values)


def _synthetic_study(study_id: str, modality: str) -> Study:
    rng = _rng(study_id, "build")
    n_series = rng.randint(1, 4)
    records = []
    for s in range(n_series):
        rows, cols = rng.choice([(512, 512), (256, 256), (1024, 1024)])
        records.append(
            DicomRecord(
                patient_id=hashlib.sha256(f"pt-{study_id}-{s}".encode()).hexdigest()[:16],
                modality=modality,
                study_date="20260502",
                series_number=s + 1,
                rows=rows,
                columns=cols,
                pixel_data=_synthetic_pixel_data(rows // 8, cols // 8, rng),
                metadata={"InstitutionName": "General Hospital", "StudyDescription": study_id},
            )
        )
    return Study(study_id=study_id, records=tuple(records))


# ----------------------------------------------------------------- analysis knots


class WindowingAnalyser(Knot):
    """Determines optimal windowing parameters from pixel statistics.

    In a real pipeline this would use the float32 pixel array from
    DicomRecord.pixel_data, compute histogram percentiles, and choose a
    window level and width appropriate for the modality.
    """

    _MODALITY_WINDOWS: ClassVar[dict[str, tuple[float, float]]] = {
        "CT": (40.0, 400.0),
        "MRI": (128.0, 256.0),
        "XR": (2048.0, 4096.0),
        "US": (128.0, 128.0),
    }

    async def process(self, study: Study, **_: Any) -> WindowingResult:
        rng = _rng(study.study_id, "window")
        level, width = self._MODALITY_WINDOWS.get(study.modality, (128.0, 256.0))
        level += rng.uniform(-level * 0.1, level * 0.1)
        width += rng.uniform(-width * 0.05, width * 0.05)
        clipped = rng.uniform(0.001, 0.04)
        return WindowingResult(
            study_id=study.study_id,
            window_level=round(level, 1),
            window_width=round(width, 1),
            clipped_fraction=round(clipped, 4),
        )


class TissueClassifier(Knot):
    """Classifies the primary tissue type from modality and pixel statistics.

    A real implementation would pass the normalised pixel array through a
    lightweight CNN or histogram-based classifier.
    """

    _MODALITY_TISSUES: ClassVar[dict[str, list[str]]] = {
        "CT": ["lung", "bone", "soft_tissue", "liver", "brain"],
        "MRI": ["brain", "soft_tissue", "cardiac", "spine"],
        "XR": ["bone", "lung", "soft_tissue"],
        "US": ["cardiac", "soft_tissue", "liver"],
    }

    async def process(self, study: Study, **_: Any) -> TissueClassification:
        rng = _rng(study.study_id, "tissue")
        candidates = self._MODALITY_TISSUES.get(study.modality, ["soft_tissue"])
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


class AnomalyDetector(Knot):
    """Screens for imaging anomalies using statistical outlier detection.

    In production this would run a segmentation model against the pixel
    array and compare region statistics against modality-specific baselines.
    """

    _FINDING_POOL: ClassVar[dict[str, list[str]]] = {
        "lung": ["ground-glass opacity", "consolidation", "nodule (≥6mm)", "pleural effusion"],
        "bone": ["cortical irregularity", "focal lytic lesion", "sclerotic change"],
        "brain": ["focal hypodensity", "midline shift", "haemorrhagic change"],
        "soft_tissue": ["mass effect", "asymmetric density"],
        "cardiac": ["cardiomegaly", "pericardial effusion"],
        "liver": ["hepatic lesion", "biliary dilation"],
        "spine": ["compression fracture", "disc herniation"],
    }

    async def process(
        self, study: Study, tissue: TissueClassification, **_: Any
    ) -> AnomalyReport:
        rng = _rng(study.study_id, "anomaly")
        pool = self._FINDING_POOL.get(tissue.primary_tissue, ["incidental finding"])
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
        urgent = severity == "severe" or (
            severity == "moderate" and rng.random() < 0.3
        )
        return AnomalyReport(
            study_id=study.study_id,
            anomalies_found=True,
            severity=severity,
            findings=findings,
            requires_urgent_review=urgent,
        )


# ----------------------------------------------------------------- dispatcher knot


class StudyDispatcher(Knot):
    """Pulls the next study from the queue and registers parallel analysis knots.

    Each invocation wires up WindowingAnalyser, TissueClassifier, and
    AnomalyDetector in parallel, then an Aggregator, then a TriageDecider —
    all as live nodes in the extensible tapestry.
    """

    async def process(self, queue: TriageQueue, **_: Any) -> TriageQueue:
        study = queue.current_study
        new_queue = queue.evolve(study_idx=queue.study_idx + 1)

        store = get_current_store()
        if store is None:
            return new_queue

        prefix = f"study_{queue.study_idx}"

        wind = WindowingAnalyser(
            study=study,
            _config=KnotConfig(id=f"{prefix}__window", validate_io=False),
        )
        tissue = TissueClassifier(
            study=study,
            _config=KnotConfig(id=f"{prefix}__tissue", validate_io=False),
        )
        anomaly = AnomalyDetector(
            study=study,
            tissue=tissue,
            _config=KnotConfig(id=f"{prefix}__anomaly", validate_io=False),
        )
        store.register(wind)
        store.register(tissue)
        store.register(anomaly)

        agg = Aggregator(
            combine=lambda **kw: list(kw.values()),
            windowing=wind,
            tissue=tissue,
            anomalies=anomaly,
            _config=KnotConfig(id=f"{prefix}__agg", validate_io=False),
        )
        store.register(agg)

        decider = TriageDecider(
            queue=self,
            findings=agg,
            _config=KnotConfig(id=f"{prefix}__decide", validate_io=False),
        )
        store.register(decider)

        return new_queue


# ----------------------------------------------------------------- decider knot


class TriageDecider(Knot):
    """Assembles a TriageOutcome and dispatches the next study or finalises."""

    async def process(
        self,
        queue: TriageQueue,
        findings: list[Any],
        **_: Any,
    ) -> TriageQueue:
        by_type: dict[str, Any] = {}
        for item in findings:
            by_type[type(item).__name__] = item

        windowing: WindowingResult = by_type["WindowingResult"]
        tissue: TissueClassification = by_type["TissueClassification"]
        anomalies: AnomalyReport = by_type["AnomalyReport"]

        if anomalies.requires_urgent_review:
            decision = "urgent"
            rationale = (
                f"Urgent: {', '.join(anomalies.findings)} "
                f"({anomalies.severity}) in {tissue.primary_tissue}"
            )
        elif anomalies.anomalies_found:
            decision = "review"
            rationale = (
                f"Review requested: {', '.join(anomalies.findings)} "
                f"({anomalies.severity})"
            )
        else:
            decision = "routine"
            rationale = (
                f"No anomalies detected in {tissue.primary_tissue} "
                f"(confidence {tissue.confidence:.0%})"
            )

        outcome = TriageOutcome(
            study_id=windowing.study_id,
            decision=decision,
            windowing=windowing,
            tissue=tissue,
            anomalies=anomalies,
            rationale=rationale,
        )
        new_queue = queue.evolve(outcomes=(*queue.outcomes, outcome))

        store = get_current_store()
        if store is None:
            return new_queue

        if not new_queue.done:
            store.register(
                StudyDispatcher(
                    queue=self,
                    _config=KnotConfig(
                        id=f"dispatch_{new_queue.study_idx}", validate_io=False
                    ),
                )
            )
        else:
            store.register(
                _TriageReport(
                    queue=self,
                    _config=KnotConfig(id=TRIAGE_COMPLETE_ID, validate_io=False),
                )
            )

        return new_queue


@dataclass(frozen=True)
class TriageSummary:
    """Serialisable run output — strips raw pixel bytes from studies."""

    n_studies: int
    outcomes: tuple[TriageOutcome, ...]


class _TriageReport(Knot):
    """Terminal knot — surfaces outcomes without raw pixel bytes."""

    async def process(self, queue: TriageQueue, **_: Any) -> TriageSummary:
        return TriageSummary(
            n_studies=len(queue.studies),
            outcomes=queue.outcomes,
        )


# ----------------------------------------------------------------- tapestry


def build_tapestry(queue: TriageQueue | None = None, history=None) -> Tapestry:
    t = Tapestry(history=history)
    t.store.register(
        StudyDispatcher(
            queue=queue if queue is not None else make_queue(),
            _config=KnotConfig(id="dispatch_0", validate_io=False),
        )
    )
    return t


# ----------------------------------------------------------------- study queue


STUDY_MANIFEST = [
    ("chest-ct-001", "CT"),
    ("brain-mri-002", "MRI"),
    ("chest-xr-003", "XR"),
    ("cardiac-us-004", "US"),
    ("abdomen-ct-005", "CT"),
    ("spine-mri-006", "MRI"),
]


def make_queue() -> TriageQueue:
    studies = tuple(
        _synthetic_study(sid, modality) for sid, modality in STUDY_MANIFEST
    )
    return TriageQueue(studies=studies)


# ----------------------------------------------------------------- main


async def main() -> None:
    # Raw pixel bytes in intermediate knot outputs are not JSON-serialisable;
    # skip history for this example.
    queue = make_queue()
    history = SQLiteHistory(path=str(Path(__file__).parent.parent / "pirn.db"))
    t = build_tapestry(queue=queue, history=history)

    _DECISION_ICON = {"routine": "✓", "review": "⚑", "urgent": "⚠"}

    print("\n── Medical Imaging Triage Agent ──\n")
    print(f"Queue: {len(queue.studies)} studies\n")

    result = await t.run(extensible=True)

    if not result.succeeded:
        exc = result.exceptions[0] if result.exceptions else None
        print(f"FAILED: {exc.knot_id if exc else '?'}: {exc.message[:80] if exc else ''}")
        return

    final: TriageSummary = result.outputs[TRIAGE_COMPLETE_ID]

    decisions: dict[str, list[str]] = {"urgent": [], "review": [], "routine": []}
    for outcome in final.outcomes:
        icon = _DECISION_ICON[outcome.decision]
        tissue = outcome.tissue.primary_tissue
        wl = outcome.windowing.window_level
        ww = outcome.windowing.window_width
        print(
            f"{icon} [{outcome.decision.upper():7s}] {outcome.study_id}"
            f"  ({tissue}, WL={wl:.0f}/WW={ww:.0f})"
        )
        print(f"          {outcome.rationale}")
        decisions[outcome.decision].append(outcome.study_id)

    print(f"\nSummary ({final.n_studies} studies): "
          f"{len(decisions['urgent'])} urgent · "
          f"{len(decisions['review'])} review · "
          f"{len(decisions['routine'])} routine")


if __name__ == "__main__":
    asyncio.run(main())
