"""``ClinicalEvent`` — the normalised event every sub-pipeline emits.

Part of the ``examples.domain_formats.hl7v2_message_router`` example.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ClinicalEvent:
    encounter_id: str
    event_kind: str
    details: dict[str, Any]
    requires_alert: bool
