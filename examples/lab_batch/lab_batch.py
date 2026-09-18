"""Example: Lab sample batch processing with Map.

A pathology lab receives a batch of patient samples each morning.
Every sample must be independently analysed for a panel of biomarkers,
flagged if any values fall outside reference ranges, and a per-sample
report generated.  The batch summary collects all results.

Demonstrates:
- Map: apply the same multi-step analysis to every element in a list
- Parallel execution: all samples in the batch run concurrently
- Chained Maps: analyse → report as two sequential per-element stages

Topology:

    batch ──► Map(analyse_sample) ──► summarise_batch

Run with:
    uv run python -m examples.lab_batch
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.map import Map
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from examples.lab_batch.batch_summary import BatchSummary
from examples.lab_batch.knots import analyse_sample, generate_report, summarise_batch
from examples.lab_batch.raw_sample import RawSample


class LabBatch:
    """Builds and runs the mapped per-sample analysis tapestry for a lab batch."""

    _status_icon: ClassVar[dict[str, str]] = {"normal": "✓", "flagged": "⚠", "critical": "✗"}

    @staticmethod
    def build_tapestry(history: SQLiteHistory | None = None) -> Tapestry:
        """Wire batch → Map(analyse) → Map(report) → summary."""
        with Tapestry(history=history) as t:
            batch = Parameter("batch", list, _config=KnotConfig(id="batch"))

            analysed = analyse_sample(sample=Map(batch), _config=KnotConfig(id="analyse"))
            reports = generate_report(analysed=Map(analysed), _config=KnotConfig(id="report"))
            summarise_batch(reports=reports, _config=KnotConfig(id="summary"))
        return t

    @staticmethod
    def _make_batch(seed: int, n: int) -> list[RawSample]:
        """Generate ``n`` deterministic pseudo-random samples for one collection round."""
        rng = random.Random(seed)
        samples: list[RawSample] = []
        for i in range(n):
            measurements = {
                "haemoglobin": rng.gauss(145, 20),
                "white_cells": rng.gauss(7.0, 2.5),
                "platelets": rng.gauss(260, 60),
                "creatinine": rng.gauss(82, 18),
                "glucose": rng.gauss(5.2, 1.4),
            }
            samples.append(
                RawSample(
                    sample_id=f"S{seed:02d}-{i + 1:03d}",
                    patient_id=f"P{rng.randint(1000, 9999)}",
                    collected_at="2026-04-30T07:00:00Z",
                    measurements={k: round(v, 2) for k, v in measurements.items()},
                )
            )
        return samples

    @classmethod
    def _print_summary(cls, label: str, summary: BatchSummary) -> None:
        """Print the per-status counts and one line per report."""
        print(f"\n── {label} ({summary.total} samples) ──")
        print(f"  normal={summary.normal}  flagged={summary.flagged}  critical={summary.critical}")
        for report in summary.reports:
            icon = cls._status_icon[report.status]
            print(f"  {icon} {report.sample_id}  {report.narrative[:70]}")

    @classmethod
    async def main(cls) -> None:
        """Run the morning and afternoon batches and print both summaries."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[1] / "pirn.db"))
        t = cls.build_tapestry(history=history)

        morning_batch = cls._make_batch(seed=1, n=8)
        afternoon_batch = cls._make_batch(seed=2, n=5)

        # Morning run — 8 samples
        r1 = await t.run(RunRequest(parameters={"batch": morning_batch}))
        summary1: BatchSummary = r1.outputs["summary"]
        cls._print_summary("Morning batch", summary1)

        # Afternoon run — 5 new samples
        r2 = await t.run(RunRequest(parameters={"batch": afternoon_batch}))
        summary2: BatchSummary = r2.outputs["summary"]
        cls._print_summary("Afternoon batch", summary2)

        history.close()
