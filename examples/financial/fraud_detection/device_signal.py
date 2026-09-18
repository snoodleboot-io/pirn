"""``DeviceSignal`` — optional device-fingerprint signal.

Part of the ``examples.financial.fraud_detection`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeviceSignal:
    """Device fingerprint match against known fraud devices."""

    known_fraud_device: bool
    device_age_days: int
