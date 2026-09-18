"""``FraudDecision`` — the final verdict for one transaction.

Part of the ``examples.financial.fraud_detection`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FraudDecision:
    txn_id: str
    verdict: str  # "approved" | "review" | "blocked"
    score: float
    reasons: list[str]
    signals_used: list[str]
