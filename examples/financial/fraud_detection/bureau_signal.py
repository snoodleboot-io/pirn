"""``BureauSignal`` — optional third-party fraud bureau signal.

Part of the ``examples.financial.fraud_detection`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BureauSignal:
    """Third-party fraud bureau lookup score."""

    bureau_score: float  # 0.0-1.0 (higher = more likely fraud)
    blacklisted: bool
