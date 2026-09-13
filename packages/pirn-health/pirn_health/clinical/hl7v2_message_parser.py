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

Note:
    ``_is_stub`` is ``True`` on this knot: it is a functional placeholder
    for the production implementation described above, not a complete
    algorithm. It is registered so pipelines can be wired and tested
    end-to-end before the real implementation lands; do not treat its
    output as production-quality.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.types.clinical_record import ClinicalRecord


class HL7v2MessageParser(Knot):
    """Parse one HL7v2 message into a :class:`ClinicalRecord`."""

    _is_stub: ClassVar[bool] = True

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

        # PID-3: patient identifier list; PID-2 fallback
        patient_id = self._field(segments, "PID", 3) or self._field(segments, "PID", 2) or ""
        # PV1-19: visit number as encounter ID; MSH-10 (message control ID) as fallback
        encounter_id = self._field(segments, "PV1", 19) or self._field(segments, "MSH", 10) or ""

        # OBX-3: observation identifier (component 0 = code, component 2 = display)
        observation_codes = tuple(
            self._field(segments, "OBX", 3, component=0, occurrence=i)
            for i in range(len(segments.get("OBX", [])))
            if self._field(segments, "OBX", 3, component=0, occurrence=i)
        )

        # MSH-7: message date/time (format YYYYMMDDHHMMSS or YYYYMMDD)
        dt_raw = self._field(segments, "MSH", 7)
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

    @staticmethod
    def _field(
        segments: dict[str, list[list[str]]],
        seg: str,
        field_idx: int,
        component: int = 0,
        occurrence: int = 0,
    ) -> str:
        rows = segments.get(seg, [])
        if occurrence >= len(rows):
            return ""
        fields = rows[occurrence]
        if field_idx >= len(fields):
            return ""
        components = fields[field_idx].split("^")
        return components[component].strip() if component < len(components) else ""
