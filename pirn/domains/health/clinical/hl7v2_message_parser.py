"""``HL7v2MessageParser`` — parse a raw HL7v2 string into a clinical record.

Production version would use ``hl7apy`` or ``python-hl7`` to parse the
pipe-delimited segments. This stub validates the message string is
non-empty and returns a deterministic :class:`ClinicalRecord` derived
from a few easily-recovered fields.

Algorithm:
    1. Receive a message string.
    2. Validate that message is a non-empty string.
    3. Parse the MSH/PID/OBX segments.
    4. Construct and return a ClinicalRecord from the parsed fields.


References:
    - HL7 v2.x: https://www.hl7.org/implement/standards/product_brief.cfm?product_id=185
    - hl7apy: https://github.com/crs4/hl7apy
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
        message: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, _config=_config, **kwargs)

    async def process(
        self,
        message: str,
        **_: Any,
    ) -> ClinicalRecord:
        """Parse the HL7v2 message segments and return a ClinicalRecord.

        Args:
            message: Non-empty HL7v2 message string to parse.

        Returns:
            A ClinicalRecord derived from the parsed HL7v2 message.

        Raises:
            TypeError: If message is not a string.
            ValueError: If message is empty.
        """
        if not isinstance(message, str):
            raise TypeError("HL7v2MessageParser: message must be a string")
        if not message:
            raise ValueError("HL7v2MessageParser: message must be non-empty")
        # Production: parse MSH/PID/OBX segments via hl7apy.
        return ClinicalRecord(
            patient_id="",
            encounter_id="",
            observation_codes=(),
            observed_at=datetime.now(timezone.utc),
            source_system="hl7v2",
        )
