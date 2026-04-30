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
    uv run python examples/financial/fraud_detection.py
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from pathlib import Path

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.result import Ok, Result
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

# ----------------------------------------------------------------- models


@dataclass
class Transaction:
    txn_id: str
    account_id: str
    amount: float
    merchant: str
    country: str
    device_id: str | None


@dataclass
class CoreRisk:
    """Velocity, amount, and account-history based risk signal — always present."""

    score: float  # 0.0-1.0
    velocity_flag: bool  # >5 transactions in 10 min
    amount_flag: bool  # unusually large for this account


@dataclass
class DeviceSignal:
    """Device fingerprint match against known fraud devices."""

    known_fraud_device: bool
    device_age_days: int


@dataclass
class GeoSignal:
    """Country-of-transaction vs. account home-country cross-reference."""

    country_mismatch: bool
    high_risk_country: bool


@dataclass
class BureauSignal:
    """Third-party fraud bureau lookup score."""

    bureau_score: float  # 0.0-1.0 (higher = more likely fraud)
    blacklisted: bool


@dataclass
class FraudDecision:
    txn_id: str
    verdict: str  # "approved" | "review" | "blocked"
    score: float
    reasons: list[str]
    signals_used: list[str]


# ----------------------------------------------------------------- knots


@knot
async def core_analysis(txn: Transaction) -> CoreRisk:
    """Required: velocity checks and account-history risk scoring."""
    rng = random.Random(txn.txn_id)
    score = rng.uniform(0.05, 0.55)
    velocity_flag = txn.amount > 500 and rng.random() > 0.7
    amount_flag = txn.amount > 2000
    if velocity_flag or amount_flag:
        score += 0.2
    return CoreRisk(
        score=min(score, 1.0),
        velocity_flag=velocity_flag,
        amount_flag=amount_flag,
    )


@knot
async def device_check(txn: Transaction) -> DeviceSignal:
    """Optional: fingerprint device_id against known fraud device registry."""
    if txn.device_id is None:
        raise ValueError("no device_id present — mobile web checkout")
    rng = random.Random(txn.device_id)
    return DeviceSignal(
        known_fraud_device=rng.random() > 0.92,
        device_age_days=rng.randint(1, 1200),
    )


@knot
async def geo_check(txn: Transaction) -> GeoSignal:
    """Optional: compare transaction country against account home country."""
    HIGH_RISK = {"NG", "RU", "KP", "IR"}
    home = {"ACC-001": "GB", "ACC-002": "US", "ACC-003": "DE"}.get(txn.account_id, "GB")
    mismatch = txn.country != home
    return GeoSignal(
        country_mismatch=mismatch,
        high_risk_country=txn.country in HIGH_RISK,
    )


@knot
async def bureau_check(txn: Transaction) -> BureauSignal:
    """Optional: third-party fraud bureau lookup — may be rate-limited."""
    rng = random.Random(txn.txn_id + "bureau")
    if rng.random() > 0.75:
        raise RuntimeError("bureau API rate limit exceeded — retry later")
    return BureauSignal(
        bureau_score=rng.uniform(0.0, 0.8),
        blacklisted=rng.random() > 0.97,
    )


@knot
async def decide(
    txn: Result[Transaction],
    core: Result[CoreRisk],
    device: Result[DeviceSignal],
    geo: Result[GeoSignal],
    bureau: Result[BureauSignal],
) -> FraudDecision:
    """Combine all available signals into a final fraud verdict.

    With RECEIVE_ERRORS, every parent arrives as a Result — Ok, Err, or
    Skipped.  txn and core are expected to always be Ok (if either fails,
    we raise and the pipeline records this knot as Err).  The others are
    truly optional: we use their values only when Ok and proceed without
    them otherwise.
    """
    if not isinstance(txn, Ok):
        raise RuntimeError(f"transaction unavailable: {txn}")
    if not isinstance(core, Ok):
        raise RuntimeError(f"core analysis failed: {core}")
    txn_val: Transaction = txn.value
    core_val: CoreRisk = core.value

    score = core_val.score
    reasons: list[str] = []
    signals_used = ["core"]

    if core_val.velocity_flag:
        reasons.append("velocity")
    if core_val.amount_flag:
        reasons.append("large_amount")

    if isinstance(device, Ok):
        signals_used.append("device")
        if device.value.known_fraud_device:
            score += 0.35
            reasons.append("fraud_device")
        elif device.value.device_age_days < 7:
            score += 0.1
            reasons.append("new_device")

    if isinstance(geo, Ok):
        signals_used.append("geo")
        if geo.value.high_risk_country:
            score += 0.25
            reasons.append("high_risk_country")
        elif geo.value.country_mismatch:
            score += 0.1
            reasons.append("country_mismatch")

    if isinstance(bureau, Ok):
        signals_used.append("bureau")
        if bureau.value.blacklisted:
            score += 0.5
            reasons.append("blacklisted")
        elif bureau.value.bureau_score > 0.6:
            score += bureau.value.bureau_score * 0.2
            reasons.append("high_bureau_score")

    score = min(score, 1.0)
    if score >= 0.7:
        verdict = "blocked"
    elif score >= 0.4:
        verdict = "review"
    else:
        verdict = "approved"

    return FraudDecision(
        txn_id=txn_val.txn_id,
        verdict=verdict,
        score=round(score, 3),
        reasons=reasons,
        signals_used=signals_used,
    )


# ----------------------------------------------------------------- pipeline


def build_tapestry(history=None) -> Tapestry:
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


# ----------------------------------------------------------------- main


_VERDICT_ICON = {"approved": "✓", "review": "⚠", "blocked": "✗"}

TRANSACTIONS = [
    Transaction("TXN-001", "ACC-001", 85.00, "Amazon UK", "GB", "DEV-aaa"),
    Transaction("TXN-002", "ACC-001", 3500.00, "Luxury Goods", "AE", "DEV-bbb"),
    Transaction("TXN-003", "ACC-002", 12.99, "Netflix", "US", None),
    Transaction("TXN-004", "ACC-003", 250.00, "Electronics", "RU", "DEV-ccc"),
    Transaction("TXN-005", "ACC-002", 9999.00, "Wire Transfer", "NG", "DEV-ddd"),
]


async def main() -> None:
    history = SQLiteHistory(path=str(Path(__file__).parent.parent / "pirn.db"))
    t = build_tapestry(history=history)

    print("\n── Transaction fraud decisions ──")
    print(f"{'TXN':<10} {'VERDICT':<10} {'SCORE':<7} {'SIGNALS':<28} REASONS")
    print("─" * 75)

    for txn in TRANSACTIONS:
        result = await t.run(RunRequest(parameters={"txn": txn}))
        # decide is the authoritative outcome — optional knots (device/geo/bureau)
        # may have failed, which is expected and handled inside decide.
        if "decide" in result.outputs:
            d: FraudDecision = result.outputs["decide"]
            icon = _VERDICT_ICON[d.verdict]
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
                f"{icon} {txn.txn_id:<8} {d.verdict:<10} {d.score:<7} {signals:<28} {reasons}{note}"
            )
        else:
            exc = result.exceptions[0]
            print(f"✗ {txn.txn_id:<8} PIPELINE FAILED  {exc.knot_id}: {exc.message[:40]}")

    history.close()


if __name__ == "__main__":
    asyncio.run(main())
