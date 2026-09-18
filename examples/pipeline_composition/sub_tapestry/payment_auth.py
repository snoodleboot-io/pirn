"""``PaymentAuth`` — result of the inner payment authorization.

Part of the ``examples.pipeline_composition.sub_tapestry`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PaymentAuth:
    authorized: bool
    auth_code: str
    amount: float
