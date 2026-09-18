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

The pipeline itself is the same ETL as the ``simple_etl`` example.  The
transport is an infrastructure concern and does not touch business logic
at all.

Run with:
    uv run python -m examples.data_pipeline.transport_layers
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.core.transport.data_transport import DataTransport
from pirn.core.transport.dual_write_transport import DualWriteTransport
from pirn.core.transport.filesystem_transport import FilesystemTransport
from pirn.core.transport.inline_transport import InlineTransport
from pirn.tapestry import Tapestry

from examples.data_pipeline.transport_layers.knots import ingest, score, summarise
from examples.data_pipeline.transport_layers.report import Report


class TransportLayers:
    """Runs the same ETL tapestry under three different transports."""

    _params: ClassVar[dict[str, object]] = {
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

    @staticmethod
    def build_tapestry(
        history: SQLiteHistory | None = None,
        transport: DataTransport | None = None,
    ) -> Tapestry:
        """Wire ingest → score → summarise behind three parameters."""
        with Tapestry(history=history, transport=transport) as t:
            source_csv = Parameter("source_csv", str, _config=KnotConfig(id="source_csv"))
            score_field = Parameter("score_field", str, _config=KnotConfig(id="score_field"))
            threshold = Parameter("threshold", float, _config=KnotConfig(id="threshold"))

            raw = ingest(source_csv=source_csv, _config=KnotConfig(id="ingest"))
            scored = score(raw=raw, score_field=score_field, _config=KnotConfig(id="score"))
            summarise(scored=scored, threshold=threshold, _config=KnotConfig(id="summarise"))
        return t

    @classmethod
    async def run_inline(cls, history: SQLiteHistory) -> None:
        """Baseline: every knot output stays in process memory."""
        print("\n── InlineTransport (default) ──────────────────────────────────")
        t = cls.build_tapestry(history=history, transport=InlineTransport())
        result = await t.run(RunRequest(parameters=dict(cls._params)))
        cls._print_result(result, transport_label="inline (in-process memory)")

    @classmethod
    async def run_filesystem(cls, history: SQLiteHistory, tmp_dir: Path) -> None:
        """Serialise every knot output to a run-scoped directory on disk."""
        print("\n── FilesystemTransport ────────────────────────────────────────")
        transport = FilesystemTransport(
            base_dir=tmp_dir / "fs_transport",
            sweep_on_startup=True,
            min_free_gb=None,
        )
        t = cls.build_tapestry(history=history, transport=transport)
        result = await t.run(RunRequest(parameters=dict(cls._params)))
        cls._print_result(result, transport_label=f"filesystem ({tmp_dir / 'fs_transport'})")

        # After end_run the per-run directory is cleaned up.  Demonstrate that
        # a second run with changed inputs re-executes correctly.
        params_changed = {**cls._params, "threshold": 0.8}
        result2 = await t.run(RunRequest(parameters=params_changed))
        report: Report = result2.outputs["summarise"]
        print(
            f"  Re-run (threshold=0.8): high={report.high_value_count}, "
            f"low={report.low_value_count}"
        )

    @classmethod
    async def run_dual_write(cls, history: SQLiteHistory, tmp_dir: Path) -> None:
        """Keep a fast in-process copy and an on-disk mirror of every output."""
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
        t = cls.build_tapestry(history=history, transport=transport)
        result = await t.run(RunRequest(parameters=dict(cls._params)))
        cls._print_result(result, transport_label="dual (inline primary, filesystem mirror)")

        mirror_dir = tmp_dir / "dual_mirror"
        run_dirs = [d for d in mirror_dir.iterdir() if d.is_dir()] if mirror_dir.exists() else []
        print(f"  Mirror run directories on disk: {len(run_dirs)}")

    @staticmethod
    def _print_result(result: RunResult, *, transport_label: str) -> None:
        """Print the report and the per-knot lineage for one run."""
        report: Report = result.outputs["summarise"]
        print(f"  Transport : {transport_label}")
        print(
            f"  Report    : high={report.high_value_count}, low={report.low_value_count}, "
            f"mean_score={report.mean_score}"
        )
        for rec in result.lineage:
            print(
                f"  {rec.knot_id:<12} outcome={rec.outcome:<8} "
                f"error_policy={rec.extra.get('error_policy', '—')}"
            )

    @classmethod
    async def main(cls) -> None:
        """Run the ETL under each of the three transports in turn."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            await cls.run_inline(history)
            await cls.run_filesystem(history, tmp_path)
            await cls.run_dual_write(history, tmp_path)
