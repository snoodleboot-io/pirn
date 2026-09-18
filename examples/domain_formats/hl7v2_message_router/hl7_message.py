"""``Hl7Message`` — one decoded HL7v2 message: its type and its segments.

Part of the ``examples.domain_formats.hl7v2_message_router`` example.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Hl7Message:
    message_type: str
    segments: list[dict[str, Any]]
    encounter_id: str
