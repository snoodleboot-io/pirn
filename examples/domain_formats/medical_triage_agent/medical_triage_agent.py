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

    Replace ``Study.synthetic()`` with bytes decoded by ``DicomFormat``:

        from pirn.connectors.file_formats.dicom_format import DicomFormat

        fmt = DicomFormat()
        records = await fmt.decode(dicom_bytes)   # one record per DICOM file

    The record schema each knot expects matches DicomFormat output exactly:
        patient_id, modality, study_date, series_number,
        rows, columns, pixel_data (float32 bytes), metadata.

Run with:
    uv run python -m examples.domain_formats.medical_triage_agent
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from examples.domain_formats.medical_triage_agent.study import Study
from examples.domain_formats.medical_triage_agent.study_dispatcher import StudyDispatcher
from examples.domain_formats.medical_triage_agent.triage_ids import TriageIds
from examples.domain_formats.medical_triage_agent.triage_queue import TriageQueue
from examples.domain_formats.medical_triage_agent.triage_summary import TriageSummary


class MedicalTriageAgent:
    """Builds the study queue, runs the extensible triage tapestry, prints the verdicts."""

    _study_manifest: ClassVar[tuple[tuple[str, str], ...]] = (
        ("chest-ct-001", "CT"),
        ("brain-mri-002", "MRI"),
        ("chest-xr-003", "XR"),
        ("cardiac-us-004", "US"),
        ("abdomen-ct-005", "CT"),
        ("spine-mri-006", "MRI"),
    )
    _decision_icon: ClassVar[dict[str, str]] = {"routine": "✓", "review": "⚑", "urgent": "⚠"}

    @classmethod
    def make_queue(cls) -> TriageQueue:
        """Build the synthetic study queue named by ``_study_manifest``."""
        studies = tuple(
            Study.synthetic(study_id, modality) for study_id, modality in cls._study_manifest
        )
        return TriageQueue(studies=studies)

    @classmethod
    def build_tapestry(
        cls,
        queue: TriageQueue | None = None,
        history: SQLiteHistory | None = None,
    ) -> Tapestry:
        """Seed a tapestry with the first dispatcher; the run grows the rest."""
        t = Tapestry(history=history)
        t.store.register(
            StudyDispatcher(
                queue=queue if queue is not None else cls.make_queue(),
                _config=KnotConfig(id="dispatch_0", validate_io=False),
            )
        )
        return t

    @classmethod
    async def main(cls) -> None:
        """Triage every study in the queue and print the decisions."""
        queue = cls.make_queue()
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))
        t = cls.build_tapestry(queue=queue, history=history)

        print("\n── Medical Imaging Triage Agent ──\n")
        print(f"Queue: {len(queue.studies)} studies\n")

        result = await t.run(extensible=True)

        if not result.succeeded:
            exc = result.exceptions[0] if result.exceptions else None
            print(f"FAILED: {exc.knot_id if exc else '?'}: {exc.message[:80] if exc else ''}")
            return

        final: TriageSummary = result.outputs[TriageIds.complete]

        decisions: dict[str, list[str]] = {"urgent": [], "review": [], "routine": []}
        for outcome in final.outcomes:
            icon = cls._decision_icon[outcome.decision]
            tissue = outcome.tissue.primary_tissue
            wl = outcome.windowing.window_level
            ww = outcome.windowing.window_width
            print(
                f"{icon} [{outcome.decision.upper():7s}] {outcome.study_id}"
                f"  ({tissue}, WL={wl:.0f}/WW={ww:.0f})"
            )
            print(f"          {outcome.rationale}")
            decisions[outcome.decision].append(outcome.study_id)

        print(
            f"\nSummary ({final.n_studies} studies): "
            f"{len(decisions['urgent'])} urgent · "
            f"{len(decisions['review'])} review · "
            f"{len(decisions['routine'])} routine"
        )
