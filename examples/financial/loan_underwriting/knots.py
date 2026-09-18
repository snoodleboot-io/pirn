"""Knot factories for the ``examples.financial.loan_underwriting`` example."""

from __future__ import annotations

import random

from pirn.core.knot_factory import KnotFactory

from examples.financial.loan_underwriting.application import Application
from examples.financial.loan_underwriting.risk_profile import RiskProfile
from examples.financial.loan_underwriting.underwriting_decision import UnderwritingDecision


@KnotFactory.knot
async def assess_risk(app: Application) -> RiskProfile:
    """Score the application and assign a risk tier."""
    dti = (app.existing_debt + app.requested_amount * 0.07) / max(app.annual_income, 1)
    ltv = app.requested_amount / max(app.annual_income, 1)

    if app.credit_score >= 720 and dti < 0.36 and app.employment_years >= 2:
        tier = "prime"
    elif app.credit_score >= 620 and dti < 0.50:
        tier = "near_prime"
    else:
        tier = "subprime"

    return RiskProfile(
        app_id=app.app_id,
        tier=tier,
        dti_ratio=round(dti, 3),
        ltv_ratio=round(ltv, 3),
        credit_score=app.credit_score,
    )


@KnotFactory.knot
async def prime_underwrite(app: Application, profile: RiskProfile) -> UnderwritingDecision:
    """Prime track: standard automated approval, lowest rates."""
    approved = profile.dti_ratio < 0.43 and profile.credit_score >= 720
    return UnderwritingDecision(
        app_id=app.app_id,
        track="prime",
        approved=approved,
        offered_amount=app.requested_amount if approved else 0,
        interest_rate=4.9 if approved else 0,
        term_months=360,
        conditions=[] if approved else ["declined: dti or credit threshold"],
    )


@KnotFactory.knot
async def near_prime_underwrite(app: Application, profile: RiskProfile) -> UnderwritingDecision:
    """Near-prime track: reduced amount, higher rate, may require co-signer."""
    max_amount = min(app.requested_amount, app.annual_income * 3.5)
    approved = profile.dti_ratio < 0.50 and profile.credit_score >= 620
    conditions = []
    if app.annual_income < 40_000:
        conditions.append("co-signer required")
    if profile.dti_ratio > 0.42:
        conditions.append("reduced term only")
        term = 180
    else:
        term = 360
    return UnderwritingDecision(
        app_id=app.app_id,
        track="near_prime",
        approved=approved,
        offered_amount=round(max_amount, 2) if approved else 0,
        interest_rate=8.75 if approved else 0,
        term_months=term,
        conditions=conditions,
    )


@KnotFactory.knot
async def subprime_underwrite(app: Application, profile: RiskProfile) -> UnderwritingDecision:
    """Subprime track: manual review, heavily restricted terms, or decline."""
    rng = random.Random(app.app_id)
    # Subprime approvals are uncommon and require manual sign-off
    approved = profile.credit_score >= 580 and profile.dti_ratio < 0.55 and rng.random() > 0.4
    max_amount = min(app.requested_amount, app.annual_income * 2.0)
    return UnderwritingDecision(
        app_id=app.app_id,
        track="subprime",
        approved=approved,
        offered_amount=round(max_amount * 0.8, 2) if approved else 0,
        interest_rate=14.5 if approved else 0,
        term_months=120,
        conditions=["manual review required", "higher rate tier"]
        if approved
        else ["declined: insufficient creditworthiness"],
    )
