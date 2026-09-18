"""``ClinicalOrder`` — the OBR fields of an ORM order message.

Part of the ``examples.domain_formats.hl7v2_message_router`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ClinicalOrder:
    encounter_id: str
    order_id: str
    order_type: str
    priority: str
    ordered_by: str
    test_codes: list[str]
