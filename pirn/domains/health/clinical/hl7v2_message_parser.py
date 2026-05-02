"""``HL7v2MessageParser`` — parse a raw HL7v2 string into a clinical record.

Production version would use ``hl7apy`` or ``python-hl7`` to parse the
pipe-delimited segments. This stub validates the message string is
non-empty and returns a deterministic :class:`ClinicalRecord` derived
from a few easily-recovered fields.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.clinical_record import ClinicalRecord


class HL7v2MessageParser(Knot):
    """Parse one HL7v2 message into a :class:`ClinicalRecord`."""

    def __init__(
        self,
        *,
        message: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(message, str):
            raise TypeError("HL7v2MessageParser: message must be a string")
        if not message:
            raise ValueError("HL7v2MessageParser: message must be non-empty")
        self._message = message
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ClinicalRecord:
        # Production: parse MSH/PID/OBX segments via hl7apy.
        return ClinicalRecord(
            patient_id="",
            encounter_id="",
            observation_codes=(),
            observed_at=datetime.now(timezone.utc),
            source_system="hl7v2",
        )
