"""``Application`` — one submitted loan application.

Part of the ``examples.financial.loan_underwriting`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Application:
    app_id: str
    applicant: str
    requested_amount: float
    annual_income: float
    credit_score: int  # 300-850
    existing_debt: float
    employment_years: float
