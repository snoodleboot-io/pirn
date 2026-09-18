"""Knot factories for the ``examples.data_pipeline.transport_layers`` example."""

from __future__ import annotations

import csv
import io

from pirn.core.knot_factory import KnotFactory

from examples.data_pipeline.transport_layers.raw_batch import RawBatch
from examples.data_pipeline.transport_layers.report import Report
from examples.data_pipeline.transport_layers.scored_batch import ScoredBatch


@KnotFactory.knot
async def ingest(source_csv: str) -> RawBatch:
    reader = csv.DictReader(io.StringIO(source_csv))
    rows = list(reader)
    return RawBatch(rows=rows, row_count=len(rows))


@KnotFactory.knot
async def score(raw: RawBatch, score_field: str) -> ScoredBatch:
    """Attach a numeric score to each row, normalised to [0, 1]."""
    scored = []
    raw_values = [float(r[score_field]) for r in raw.rows]
    max_val = max(raw_values) if raw_values else 1.0
    for row, val in zip(raw.rows, raw_values, strict=True):
        scored.append({**row, "score": round(val / max_val, 4)})
    mean = round(sum(r["score"] for r in scored) / len(scored), 4) if scored else 0.0
    return ScoredBatch(rows=scored, mean_score=mean)


@KnotFactory.knot
async def summarise(scored: ScoredBatch, threshold: float) -> Report:
    high = sum(1 for r in scored.rows if r["score"] >= threshold)
    low = len(scored.rows) - high
    return Report(high_value_count=high, low_value_count=low, mean_score=scored.mean_score)
