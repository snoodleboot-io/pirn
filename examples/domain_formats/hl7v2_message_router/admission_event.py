"""``AdmissionEvent`` — the PV1 fields of an ADT admission or discharge.

Part of the ``examples.domain_formats.hl7v2_message_router`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AdmissionEvent:
    encounter_id: str
    event_type: str  # "admission" / "discharge"
    department: str
    acuity: str
    bed_id: str
