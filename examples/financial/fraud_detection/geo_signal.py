"""``GeoSignal`` — optional geolocation cross-reference signal.

Part of the ``examples.financial.fraud_detection`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GeoSignal:
    """Country-of-transaction vs. account home-country cross-reference."""

    country_mismatch: bool
    high_risk_country: bool
