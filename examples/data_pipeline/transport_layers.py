"""Example: Transport layers — controlling where knot outputs live.

By default pirn uses ``InlineTransport``: every knot output is held
in-process memory.  That is fine for small pipelines, but breaks down
when outputs are large, when the process may crash mid-run and you want
to resume, or when you want an archive copy alongside a fast local copy.

This example shows three configurations:

1. ``InlineTransport`` (default) — baseline; outputs live in memory.
2. ``FilesystemTransport`` — every knot output is serialised to disk,
   run-scoped, and cleaned up automatically on completion.  A crash
   leaves the directory behind; the next run's startup sweep removes it.
3. ``DualWriteTransport(primary=InlineTransport, mirror=FilesystemTransport)``
   — writes to both simultaneously so the in-process copy stays fast
   while the on-disk copy acts as an audit trail or crash-recovery store.
   Reads are always served from the primary.

The pipeline itself is the same ETL from simple_etl.py.  The transport
is an infrastructure concern and does not touch business logic at all.

Run with:
    uv run python examples/data_pipeline/transport_layers.py
"""

import asyncio
import csv
import io
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.transport.dual_write_transport import DualWriteTransport
from pirn.core.transport.filesystem_transport import FilesystemTransport
from pirn.core.transport.inline_transport import InlineTransport
from pirn.tapestry import Tapestry

# ----------------------------------------------------------------- models


@dataclass
class RawBatch:
    rows: list[dict[str, str]]
    row_count: int


@dataclass
class ScoredBatch:
    rows: list[dict]
    mean_score: float


@dataclass
class Report:
    high_value_count: int
    low_value_count: int
    mean_score: float


# ----------------------------------------------------------------- knots


@knot
async def ingest(source_csv: str) -> RawBatch:
    reader = csv.DictReader(io.StringIO(source_csv))
    rows = list(reader)
    return RawBatch(rows=rows, row_count=len(rows))


@knot
async def score(raw: RawBatch, score_field: str) -> ScoredBatch:
    """Attach a numeric score to each row, normalised to [0, 1]."""
    scored = []
    raw_values = [float(r[score_field]) for r in raw.rows]
    max_val = max(raw_values) if raw_values else 1.0
    for row, val in zip(raw.rows, raw_values, strict=True):
        scored.append({**row, "score": round(val / max_val, 4)})
    mean = round(sum(r["score"] for r in scored) / len(scored), 4) if scored else 0.0
    return ScoredBatch(rows=scored, mean_score=mean)


@knot
async def summarise(scored: ScoredBatch, threshold: float) -> Report:
    high = sum(1 for r in scored.rows if r["score"] >= threshold)
    low = len(scored.rows) - high
    return Report(high_value_count=high, low_value_count=low, mean_score=scored.mean_score)


# ----------------------------------------------------------------- wiring


def build_tapestry(history=None, transport=None) -> Tapestry:
    with Tapestry(history=history, transport=transport) as t:
        source_csv = Parameter("source_csv", str, _config=KnotConfig(id="source_csv"))
        score_field = Parameter("score_field", str, _config=KnotConfig(id="score_field"))
        threshold = Parameter("threshold", float, _config=KnotConfig(id="threshold"))

        raw = ingest(source_csv=source_csv, _config=KnotConfig(id="ingest"))
        scored = score(raw=raw, score_field=score_field, _config=KnotConfig(id="score"))
        summarise(scored=scored, threshold=threshold, _config=KnotConfig(id="summarise"))
    return t


PARAMS: dict = {
    "source_csv": """\
id,name,revenue
1,alpha,8200
2,beta,3100
3,gamma,9750
4,delta,1400
5,epsilon,5600
""",
    "score_field": "revenue",
    "threshold": 0.5,
}


# ----------------------------------------------------------------- demo


async def run_inline(history) -> None:
    print("\n── InlineTransport (default) ──────────────────────────────────")
    t = build_tapestry(history=history, transport=InlineTransport())
    result = await t.run(RunRequest(parameters=PARAMS))
    _print_result(result, transport_label="inline (in-process memory)")


async def run_filesystem(history, tmp_dir: Path) -> None:
    print("\n── FilesystemTransport ────────────────────────────────────────")
    transport = FilesystemTransport(
        base_dir=tmp_dir / "fs_transport",
        sweep_on_startup=True,
        min_free_gb=None,
    )
    t = build_tapestry(history=history, transport=transport)
    result = await t.run(RunRequest(parameters=PARAMS))
    _print_result(result, transport_label=f"filesystem ({tmp_dir / 'fs_transport'})")

    # After end_run the per-run directory is cleaned up.  Demonstrate that
    # a second run with changed inputs re-executes correctly.
    params_changed = {**PARAMS, "threshold": 0.8}
    result2 = await t.run(RunRequest(parameters=params_changed))
    report: Report = result2.outputs["summarise"]
    print(f"  Re-run (threshold=0.8): high={report.high_value_count}, low={report.low_value_count}")


async def run_dual_write(history, tmp_dir: Path) -> None:
    print("\n── DualWriteTransport (inline primary + filesystem mirror) ────")
    primary = InlineTransport()
    mirror = FilesystemTransport(
        base_dir=tmp_dir / "dual_mirror",
        sweep_on_startup=False,
    )
    # mirror_errors="warn": a mirror failure logs a warning but does not
    # fail the run.  Use "raise" (default) in production.
    transport = DualWriteTransport(primary=primary, mirror=mirror, mirror_errors="warn")

    # Per-knot override: the heavy `score` output goes only through the
    # filesystem mirror for large-output scenarios; the lightweight report
    # uses the pipeline-level transport.
    t = build_tapestry(history=history, transport=transport)
    result = await t.run(RunRequest(parameters=PARAMS))
    _print_result(result, transport_label="dual (inline primary, filesystem mirror)")

    mirror_dir = tmp_dir / "dual_mirror"
    run_dirs = [d for d in mirror_dir.iterdir() if d.is_dir()] if mirror_dir.exists() else []
    print(f"  Mirror run directories on disk: {len(run_dirs)}")


def _print_result(result, *, transport_label: str) -> None:
    report: Report = result.outputs["summarise"]
    print(f"  Transport : {transport_label}")
    print(f"  Report    : high={report.high_value_count}, low={report.low_value_count}, "
          f"mean_score={report.mean_score}")
    for rec in result.lineage:
        print(f"  {rec.knot_id:<12} outcome={rec.outcome:<8} "
              f"error_policy={rec.extra.get('error_policy', '—')}")


async def main() -> None:
    history = SQLiteHistory(path=str(Path(__file__).parent.parent / "pirn.db"))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        await run_inline(history)
        await run_filesystem(history, tmp_path)
        await run_dual_write(history, tmp_path)


if __name__ == "__main__":
    asyncio.run(main())
