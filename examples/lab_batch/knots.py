"""Knot factories for the ``examples.lab_batch`` example."""

from __future__ import annotations

from pirn.core.knot_factory import KnotFactory

from examples.lab_batch.analysed_sample import AnalysedSample
from examples.lab_batch.batch_summary import BatchSummary
from examples.lab_batch.raw_sample import RawSample
from examples.lab_batch.reference_ranges import ReferenceRanges
from examples.lab_batch.sample_report import SampleReport


@KnotFactory.knot
async def analyse_sample(sample: RawSample) -> AnalysedSample:
    """Check each measurement against reference ranges and flag abnormals."""
    flags: list[str] = []
    critical = False
    for marker, value in sample.measurements.items():
        bounds = ReferenceRanges.by_marker.get(marker)
        if bounds is None:
            continue
        lo, hi = bounds
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


@KnotFactory.knot
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


@KnotFactory.knot
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
