"""``UnderwritingDecision`` — the decision produced by one underwriting track.

Part of the ``examples.financial.loan_underwriting`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UnderwritingDecision:
    app_id: str
    track: str
    approved: bool
    offered_amount: float
    interest_rate: float
    term_months: int
    conditions: list[str]
