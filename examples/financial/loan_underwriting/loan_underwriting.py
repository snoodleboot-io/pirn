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
    uv run python -m examples.financial.loan_underwriting
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.parameter import Parameter
from pirn.core.result import Result
from pirn.core.run_request import RunRequest
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.branch.branch import Branch
from pirn.tapestry import Tapestry

from examples.financial.loan_underwriting.application import Application
from examples.financial.loan_underwriting.final_decision import FinalDecision
from examples.financial.loan_underwriting.knots import (
    assess_risk,
    near_prime_underwrite,
    prime_underwrite,
    subprime_underwrite,
)
from examples.financial.loan_underwriting.risk_profile import RiskProfile
from examples.financial.loan_underwriting.underwriting_decision import UnderwritingDecision


class LoanUnderwriting:
    """Builds and runs the branch-and-aggregate underwriting tapestry."""

    _applications: ClassVar[tuple[Application, ...]] = (
        Application("APP-001", "Sarah Chen", 250_000, 95_000, 760, 12_000, 8.0),
        Application("APP-002", "Marcus Webb", 180_000, 62_000, 680, 18_000, 3.5),
        Application("APP-003", "Priya Nair", 120_000, 38_000, 640, 22_000, 1.5),
        Application("APP-004", "James Okafor", 200_000, 48_000, 590, 35_000, 0.5),
        Application("APP-005", "Elena Vasquez", 320_000, 110_000, 800, 8_000, 12.0),
        Application("APP-006", "Tom Briggs", 80_000, 28_000, 545, 41_000, 2.0),
    )

    @staticmethod
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
        if not isinstance(app, Ok):
            raise RuntimeError(f"application unavailable: {app}")

        app_val: Application = app.value
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

    @staticmethod
    def build_tapestry(history: SQLiteHistory | None = None) -> Tapestry:
        """Wire assess_risk → Branch → three tracks → Aggregator."""
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
                combine=LoanUnderwriting._merge_decisions,
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

    @classmethod
    async def main(cls) -> None:
        """Underwrite every sample application and print the decision table."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))
        t = cls.build_tapestry(history=history)

        print("\n── Loan underwriting decisions ──")
        print(
            f"{'APP':<8} {'APPLICANT':<16} {'TRACK':<12} {'RESULT':<10}"
            f" {'AMOUNT':>10}  {'RATE':>6}  CONDITIONS"
        )
        print("-" * 90)

        for app in cls._applications:
            result = await t.run(RunRequest(parameters={"app": app}))
            if "decision" in result.outputs:
                d: FinalDecision = result.outputs["decision"]
                status = "APPROVED" if d.approved else "DECLINED"
                amount = f"£{d.offered_amount:>9,.0f}" if d.approved else f"{'—':>10}"
                rate = f"{d.interest_rate:.2f}%" if d.approved else "—"
                conds = "; ".join(d.conditions) if d.conditions else "—"
                print(
                    f"{app.app_id:<8} {app.applicant:<16} {d.track:<12}"
                    f" {status:<10} {amount}  {rate:>6}  {conds}"
                )
            else:
                exc = result.exceptions[0] if result.exceptions else None
                msg = exc.message[:50] if exc else "unknown error"
                print(f"{app.app_id:<8} {app.applicant:<16} {'—':<12} FAILED     {msg}")

        history.close()
