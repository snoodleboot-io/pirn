"""``Transaction`` — the card transaction under assessment.

Part of the ``examples.financial.fraud_detection`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Transaction:
    txn_id: str
    account_id: str
    amount: float
    merchant: str
    country: str
    device_id: str | None
