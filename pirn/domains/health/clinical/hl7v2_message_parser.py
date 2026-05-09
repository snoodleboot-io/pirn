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

from datetime import UTC, datetime
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

        segments: dict[str, list[list[str]]] = {}
        for line in message.splitlines():
            line = line.strip()
            if not line:
                continue
            fields = line.split("|")
            seg_name = fields[0].upper()
            segments.setdefault(seg_name, []).append(fields)

        def _field(seg: str, field_idx: int, component: int = 0, occurrence: int = 0) -> str:
            rows = segments.get(seg, [])
            if occurrence >= len(rows):
                return ""
            fields = rows[occurrence]
            if field_idx >= len(fields):
                return ""
            components = fields[field_idx].split("^")
            return components[component].strip() if component < len(components) else ""

        # PID-3: patient identifier list; PID-2 fallback
        patient_id = _field("PID", 3) or _field("PID", 2) or ""
        # PV1-19: visit number as encounter ID; MSH-10 (message control ID) as fallback
        encounter_id = _field("PV1", 19) or _field("MSH", 10) or ""

        # OBX-3: observation identifier (component 0 = code, component 2 = display)
        observation_codes = tuple(
            _field("OBX", 3, component=0, occurrence=i)
            for i in range(len(segments.get("OBX", [])))
            if _field("OBX", 3, component=0, occurrence=i)
        )

        # MSH-7: message date/time (format YYYYMMDDHHMMSS or YYYYMMDD)
        dt_raw = _field("MSH", 7)
        observed_at = datetime.now(UTC)
        if len(dt_raw) >= 8:
            try:
                fmt = "%Y%m%d%H%M%S" if len(dt_raw) >= 14 else "%Y%m%d"
                observed_at = datetime.strptime(
                    dt_raw[: 14 if len(dt_raw) >= 14 else 8], fmt
                ).replace(tzinfo=UTC)
            except ValueError:
                pass

        return ClinicalRecord(
            patient_id=patient_id,
            encounter_id=encounter_id,
            observation_codes=observation_codes,
            observed_at=observed_at,
            source_system="hl7v2",
        )
