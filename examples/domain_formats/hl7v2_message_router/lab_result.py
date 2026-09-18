"""``LabResult`` — one OBX observation from an ORU result message.

Part of the ``examples.domain_formats.hl7v2_message_router`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LabResult:
    encounter_id: str
    order_id: str
    test_code: str
    value: str
    unit: str
    reference_range: str
    flag: str  # "H" / "L" / "N" / "C"
