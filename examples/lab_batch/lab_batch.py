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
    uv run python examples/data_pipeline/lab_batch.py
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from pathlib import Path

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.nodes.map_markers import Map
from pirn.tapestry import Tapestry

# ----------------------------------------------------------------- models

REFERENCE_RANGES = {
    "haemoglobin": (120.0, 180.0),  # g/L
    "white_cells": (4.0, 11.0),  # ×10⁹/L
    "platelets": (150.0, 400.0),  # ×10⁹/L
    "creatinine": (60.0, 110.0),  # µmol/L
    "glucose": (3.9, 6.1),  # mmol/L
}


@dataclass
class RawSample:
    sample_id: str
    patient_id: str
    collected_at: str
    measurements: dict[str, float]  # biomarker → raw value


@dataclass
class AnalysedSample:
    sample_id: str
    patient_id: str
    measurements: dict[str, float]
    flags: list[str]  # biomarkers outside reference range
    critical: bool  # any value critically abnormal


@dataclass
class SampleReport:
    sample_id: str
    patient_id: str
    status: str  # "normal" | "flagged" | "critical"
    flags: list[str]
    narrative: str


@dataclass
class BatchSummary:
    total: int
    normal: int
    flagged: int
    critical: int
    reports: list[SampleReport]


# ----------------------------------------------------------------- knots


@knot
async def analyse_sample(sample: RawSample) -> AnalysedSample:
    """Check each measurement against reference ranges and flag abnormals."""
    flags: list[str] = []
    critical = False
    for marker, value in sample.measurements.items():
        lo, hi = REFERENCE_RANGES.get(marker, (None, None))
        if lo is None:
            continue
        if value < lo or value > hi:
            flags.append(marker)
            deviation = abs(value - (lo + hi) / 2) / ((hi - lo) / 2)
            if deviation > 1.5:
                critical = True
    return AnalysedSample(
        sample_id=sample.sample_id,
        patient_id=sample.patient_id,
        measurements=sample.measurements,
        flags=flags,
        critical=critical,
    )


@knot
async def generate_report(analysed: AnalysedSample) -> SampleReport:
    """Produce a human-readable report for a single sample."""
    if analysed.critical:
        status = "critical"
        narrative = (
            f"CRITICAL — sample {analysed.sample_id} shows critically abnormal "
            f"values for: {', '.join(analysed.flags)}. Immediate review required."
        )
    elif analysed.flags:
        status = "flagged"
        narrative = (
            f"Sample {analysed.sample_id} flagged for: {', '.join(analysed.flags)}. "
            f"Values outside reference range."
        )
    else:
        status = "normal"
        narrative = f"Sample {analysed.sample_id}: all values within reference ranges."
    return SampleReport(
        sample_id=analysed.sample_id,
        patient_id=analysed.patient_id,
        status=status,
        flags=analysed.flags,
        narrative=narrative,
    )


@knot
async def summarise_batch(reports: list[SampleReport]) -> BatchSummary:
    """Aggregate per-sample reports into a batch summary."""
    counts = {"normal": 0, "flagged": 0, "critical": 0}
    for r in reports:
        counts[r.status] = counts.get(r.status, 0) + 1
    return BatchSummary(
        total=len(reports),
        normal=counts["normal"],
        flagged=counts["flagged"],
        critical=counts["critical"],
        reports=reports,
    )


# ----------------------------------------------------------------- pipeline


def build_tapestry(history=None) -> Tapestry:
    with Tapestry(history=history) as t:
        batch = Parameter("batch", list, _config=KnotConfig(id="batch"))

        analysed = analyse_sample(sample=Map(batch), _config=KnotConfig(id="analyse"))
        reports = generate_report(analysed=Map(analysed), _config=KnotConfig(id="report"))
        summarise_batch(reports=reports, _config=KnotConfig(id="summary"))
    return t


# ----------------------------------------------------------------- sample data


def _make_batch(seed: int, n: int) -> list[RawSample]:
    rng = random.Random(seed)
    samples = []
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


# ----------------------------------------------------------------- main


_STATUS_ICON = {"normal": "✓", "flagged": "⚠", "critical": "✗"}


async def main() -> None:
    history = SQLiteHistory(path=str(Path(__file__).parent.parent / "pirn.db"))
    t = build_tapestry(history=history)

    morning_batch = _make_batch(seed=1, n=8)
    afternoon_batch = _make_batch(seed=2, n=5)

    # Morning run — 8 samples
    r1 = await t.run(RunRequest(parameters={"batch": morning_batch}))
    summary1: BatchSummary = r1.outputs["summary"]
    print(f"\n── Morning batch ({summary1.total} samples) ──")
    print(f"  normal={summary1.normal}  flagged={summary1.flagged}  critical={summary1.critical}")
    for report in summary1.reports:
        icon = _STATUS_ICON[report.status]
        print(f"  {icon} {report.sample_id}  {report.narrative[:70]}")

    # Afternoon run — 5 new samples
    r2 = await t.run(RunRequest(parameters={"batch": afternoon_batch}))
    summary2: BatchSummary = r2.outputs["summary"]
    print(f"\n── Afternoon batch ({summary2.total} samples) ──")
    print(f"  normal={summary2.normal}  flagged={summary2.flagged}  critical={summary2.critical}")
    for report in summary2.reports:
        icon = _STATUS_ICON[report.status]
        print(f"  {icon} {report.sample_id}  {report.narrative[:70]}")

    history.close()


if __name__ == "__main__":
    asyncio.run(main())
