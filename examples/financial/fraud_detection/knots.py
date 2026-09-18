"""Knot factories for the ``examples.financial.fraud_detection`` example."""

from __future__ import annotations

import random

from pirn.core.knot_factory import KnotFactory
from pirn.core.ok import Ok
from pirn.core.result import Result

from examples.financial.fraud_detection.bureau_signal import BureauSignal
from examples.financial.fraud_detection.core_risk import CoreRisk
from examples.financial.fraud_detection.device_signal import DeviceSignal
from examples.financial.fraud_detection.fraud_decision import FraudDecision
from examples.financial.fraud_detection.geo_signal import GeoSignal
from examples.financial.fraud_detection.transaction import Transaction


@KnotFactory.knot
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


@KnotFactory.knot
async def device_check(txn: Transaction) -> DeviceSignal:
    """Optional: fingerprint device_id against known fraud device registry."""
    if txn.device_id is None:
        raise ValueError("no device_id present — mobile web checkout")
    rng = random.Random(txn.device_id)
    return DeviceSignal(
        known_fraud_device=rng.random() > 0.92,
        device_age_days=rng.randint(1, 1200),
    )


@KnotFactory.knot
async def geo_check(txn: Transaction) -> GeoSignal:
    """Optional: compare transaction country against account home country."""
    high_risk = {"NG", "RU", "KP", "IR"}
    home = {"ACC-001": "GB", "ACC-002": "US", "ACC-003": "DE"}.get(txn.account_id, "GB")
    mismatch = txn.country != home
    return GeoSignal(
        country_mismatch=mismatch,
        high_risk_country=txn.country in high_risk,
    )


@KnotFactory.knot
async def bureau_check(txn: Transaction) -> BureauSignal:
    """Optional: third-party fraud bureau lookup — may be rate-limited."""
    rng = random.Random(txn.txn_id + "bureau")
    if rng.random() > 0.75:
        raise RuntimeError("bureau API rate limit exceeded — retry later")
    return BureauSignal(
        bureau_score=rng.uniform(0.0, 0.8),
        blacklisted=rng.random() > 0.97,
    )


@KnotFactory.knot
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
