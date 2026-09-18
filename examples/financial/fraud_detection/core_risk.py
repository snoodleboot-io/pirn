"""``CoreRisk`` — the always-present core risk signal.

Part of the ``examples.financial.fraud_detection`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CoreRisk:
    """Velocity, amount, and account-history based risk signal — always present."""

    score: float  # 0.0-1.0
    velocity_flag: bool  # >5 transactions in 10 min
    amount_flag: bool  # unusually large for this account
