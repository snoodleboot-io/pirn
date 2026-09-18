"""Example: Transaction fraud detection with optional enrichment signals.

A fraud team runs a required core analysis on every transaction, then
enriches the decision with signals from three supplementary services —
device fingerprinting, geolocation cross-reference, and a third-party
fraud bureau.  Any of these can be unavailable, rate-limited, or simply
absent for the transaction type.  The final decision knot receives
whatever arrived and proceeds regardless.

Demonstrates:
- Optional inputs via RECEIVE_ERRORS error policy: a knot can inspect
  whether each parent produced Ok, Err, or Skipped and act accordingly
- Resilient pipelines: an external service being down degrades gracefully
  rather than cascading into a full pipeline failure
- The difference between a required signal (core analysis) and
  supplementary signals that improve but are not blocking

Topology:

    transaction ──► core_analysis ──────────────────────────────────────────► decide
                 ── device_check (may fail / be unavailable) ───────────────► decide
                 ── geo_check    (may fail / be unavailable) ────────────────► decide
                 ── bureau_check (may fail / be unavailable) ────────────────► decide

Run with:
    uv run python -m examples.financial.fraud_detection
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from examples.financial.fraud_detection.fraud_decision import FraudDecision
from examples.financial.fraud_detection.knots import (
    bureau_check,
    core_analysis,
    decide,
    device_check,
    geo_check,
)
from examples.financial.fraud_detection.transaction import Transaction


class FraudDetection:
    """Builds and runs the fraud-scoring tapestry over a batch of transactions."""

    _verdict_icon: ClassVar[dict[str, str]] = {"approved": "✓", "review": "⚠", "blocked": "✗"}

    _transactions: ClassVar[tuple[Transaction, ...]] = (
        Transaction("TXN-001", "ACC-001", 85.00, "Amazon UK", "GB", "DEV-aaa"),
        Transaction("TXN-002", "ACC-001", 3500.00, "Luxury Goods", "AE", "DEV-bbb"),
        Transaction("TXN-003", "ACC-002", 12.99, "Netflix", "US", None),
        Transaction("TXN-004", "ACC-003", 250.00, "Electronics", "RU", "DEV-ccc"),
        Transaction("TXN-005", "ACC-002", 9999.00, "Wire Transfer", "NG", "DEV-ddd"),
    )

    @staticmethod
    def build_tapestry(history: SQLiteHistory | None = None) -> Tapestry:
        """Wire the required core analysis and three optional signals into decide."""
        with Tapestry(history=history) as t:
            txn = Parameter("txn", Transaction, _config=KnotConfig(id="txn"))

            core = core_analysis(txn=txn, _config=KnotConfig(id="core"))
            device = device_check(txn=txn, _config=KnotConfig(id="device"))
            geo = geo_check(txn=txn, _config=KnotConfig(id="geo"))
            bureau = bureau_check(txn=txn, _config=KnotConfig(id="bureau"))

            decide(
                txn=txn,
                core=core,
                device=device,
                geo=geo,
                bureau=bureau,
                _config=KnotConfig(
                    id="decide",
                    validate_io=False,
                    error_policy=ErrorPolicy.RECEIVE_ERRORS,
                ),
            )
        return t

    @classmethod
    async def main(cls) -> None:
        """Score every sample transaction and print the verdict table."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))
        t = cls.build_tapestry(history=history)

        print("\n── Transaction fraud decisions ──")
        print(f"{'TXN':<10} {'VERDICT':<10} {'SCORE':<7} {'SIGNALS':<28} REASONS")
        print("─" * 75)

        for txn in cls._transactions:
            result = await t.run(RunRequest(parameters={"txn": txn}))
            # decide is the authoritative outcome — optional knots (device/geo/bureau)
            # may have failed, which is expected and handled inside decide.
            if "decide" in result.outputs:
                d: FraudDecision = result.outputs["decide"]
                icon = cls._verdict_icon[d.verdict]
                signals = "+".join(d.signals_used)
                reasons = ", ".join(d.reasons) if d.reasons else "—"
                # Show which optional signals were unavailable
                unavailable = [
                    k
                    for k in ("device", "geo", "bureau")
                    if any(e.knot_id == k for e in result.exceptions)
                ]
                note = f"  (no {', '.join(unavailable)})" if unavailable else ""
                print(
                    f"{icon} {txn.txn_id:<8} {d.verdict:<10} "
                    f"{d.score:<7} {signals:<28} {reasons}{note}"
                )
            else:
                exc = result.exceptions[0]
                print(f"✗ {txn.txn_id:<8} PIPELINE FAILED  {exc.knot_id}: {exc.message[:40]}")

        history.close()
