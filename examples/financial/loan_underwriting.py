"""Example: Loan application underwriting with Branch and Aggregator.

A loan application is assessed for risk, routed to one of three
underwriting tracks depending on the applicant's credit profile, each
track performs its own checks and produces a decision, and an aggregator
collects whichever track ran into the final application record.

The other two tracks produce Skipped — not errors — so the aggregator
handles a predictable mix of one Ok and two Skipped values cleanly.

Demonstrates:
- Branch: route a value to exactly one of N named paths based on a
  selector function; non-selected paths are automatically Skipped
- Aggregator with RECEIVE_ERRORS: collect N parents where only one will
  be Ok and the rest Skipped, merge into a unified output
- Fan-out and convergence: one result feeds multiple flows that then
  rejoin cleanly without manual None-checks or try/except

Topology:

    application ──► assess_risk ──► Branch ──► prime track    ──┐
                                           ──► near_prime track ─┼──► Aggregator ──► finalise
                                           ──► subprime track  ──┘

Run with:
    uv run python examples/financial/loan_underwriting.py
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
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.branch.branch import Branch
from pirn.tapestry import Tapestry

# ----------------------------------------------------------------- models


@dataclass
class Application:
    app_id: str
    applicant: str
    requested_amount: float
    annual_income: float
    credit_score: int  # 300–850
    existing_debt: float
    employment_years: float


@dataclass
class RiskProfile:
    app_id: str
    tier: str  # "prime" | "near_prime" | "subprime"
    dti_ratio: float  # debt-to-income
    ltv_ratio: float  # loan-to-value (amount / income)
    credit_score: int


@dataclass
class UnderwritingDecision:
    app_id: str
    track: str
    approved: bool
    offered_amount: float
    interest_rate: float
    term_months: int
    conditions: list[str]


@dataclass
class FinalDecision:
    app_id: str
    applicant: str
    track: str
    approved: bool
    offered_amount: float
    interest_rate: float
    term_months: int
    conditions: list[str]


# ----------------------------------------------------------------- knots


@knot
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


@knot
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


@knot
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


@knot
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


def _merge_decisions(
    prime: Result[UnderwritingDecision],
    near_prime: Result[UnderwritingDecision],
    subprime: Result[UnderwritingDecision],
    app: Result[Application],
    profile: Result[RiskProfile],
) -> FinalDecision:
    """Extract the one Ok decision from whichever track ran."""
    decision: UnderwritingDecision | None = None
    for result in (prime, near_prime, subprime):
        if isinstance(result, Ok):
            decision = result.value
            break

    if decision is None:
        raise RuntimeError("no underwriting track produced a decision")

    app_val: Application = app.value  # type: ignore[union-attr]
    return FinalDecision(
        app_id=decision.app_id,
        applicant=app_val.applicant,
        track=decision.track,
        approved=decision.approved,
        offered_amount=decision.offered_amount,
        interest_rate=decision.interest_rate,
        term_months=decision.term_months,
        conditions=decision.conditions,
    )


# ----------------------------------------------------------------- pipeline


def build_tapestry(history=None) -> Tapestry:
    with Tapestry(history=history) as t:
        app = Parameter("app", Application, _config=KnotConfig(id="app"))
        profile = assess_risk(app=app, _config=KnotConfig(id="profile"))

        router = Branch(
            input=profile,
            selector=lambda p: p.tier,
            branches=("prime", "near_prime", "subprime"),
            _config=KnotConfig(id="router"),
        )

        prime_dec = prime_underwrite(
            app=app,
            profile=router["prime"],
            _config=KnotConfig(id="prime"),
        )
        near_prime_dec = near_prime_underwrite(
            app=app,
            profile=router["near_prime"],
            _config=KnotConfig(id="near_prime"),
        )
        subprime_dec = subprime_underwrite(
            app=app,
            profile=router["subprime"],
            _config=KnotConfig(id="subprime"),
        )

        Aggregator(
            combine=_merge_decisions,
            prime=prime_dec,
            near_prime=near_prime_dec,
            subprime=subprime_dec,
            app=app,
            profile=profile,
            _config=KnotConfig(
                id="decision",
                validate_io=False,
                error_policy=ErrorPolicy.RECEIVE_ERRORS,
            ),
        )
    return t


# ----------------------------------------------------------------- main


APPLICATIONS = [
    Application("APP-001", "Sarah Chen", 250_000, 95_000, 760, 12_000, 8.0),
    Application("APP-002", "Marcus Webb", 180_000, 62_000, 680, 18_000, 3.5),
    Application("APP-003", "Priya Nair", 120_000, 38_000, 640, 22_000, 1.5),
    Application("APP-004", "James Okafor", 200_000, 48_000, 590, 35_000, 0.5),
    Application("APP-005", "Elena Vasquez", 320_000, 110_000, 800, 8_000, 12.0),
    Application("APP-006", "Tom Briggs", 80_000, 28_000, 545, 41_000, 2.0),
]


async def main() -> None:
    history = SQLiteHistory(path=str(Path(__file__).parent.parent / "pirn.db"))
    t = build_tapestry(history=history)

    print("\n── Loan underwriting decisions ──")
    print(
        f"{'APP':<8} {'APPLICANT':<16} {'TRACK':<12} {'RESULT':<10} {'AMOUNT':>10}  {'RATE':>6}  CONDITIONS"
    )
    print("─" * 90)

    for app in APPLICATIONS:
        result = await t.run(RunRequest(parameters={"app": app}))
        if "decision" in result.outputs:
            d: FinalDecision = result.outputs["decision"]
            status = "APPROVED" if d.approved else "DECLINED"
            amount = f"£{d.offered_amount:>9,.0f}" if d.approved else f"{'—':>10}"
            rate = f"{d.interest_rate:.2f}%" if d.approved else "—"
            conds = "; ".join(d.conditions) if d.conditions else "—"
            print(
                f"{app.app_id:<8} {app.applicant:<16} {d.track:<12} {status:<10} {amount}  {rate:>6}  {conds}"
            )
        else:
            exc = result.exceptions[0] if result.exceptions else None
            msg = exc.message[:50] if exc else "unknown error"
            print(f"{app.app_id:<8} {app.applicant:<16} {'—':<12} FAILED     {msg}")

    history.close()


if __name__ == "__main__":
    asyncio.run(main())
