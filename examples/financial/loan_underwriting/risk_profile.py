"""``RiskProfile`` — the scored risk tier an application is routed on.

Part of the ``examples.financial.loan_underwriting`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskProfile:
    app_id: str
    tier: str  # "prime" | "near_prime" | "subprime"
    dti_ratio: float  # debt-to-income
    ltv_ratio: float  # loan-to-value (amount / income)
    credit_score: int
