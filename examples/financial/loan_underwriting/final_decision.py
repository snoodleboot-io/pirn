"""``FinalDecision`` — the merged application record the aggregator emits.

Part of the ``examples.financial.loan_underwriting`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


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
