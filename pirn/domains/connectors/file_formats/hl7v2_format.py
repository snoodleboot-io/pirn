"""``Hl7v2Format`` — HL7 v2 message batch encoder/decoder.

HL7 v2 messages are pipe-delimited text; a file may contain multiple
messages separated by empty lines or consecutive MSH segments. Each
message is emitted as one record.

PHI safety
----------
The following fields are redacted (replaced with ``"[REDACTED]"``) to
prevent PHI leakage:

* PID.5 — patient name
* PID.7 — date of birth
* PID.11 — address

Install: ``pip install pirn[health]``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, ClassVar

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)

class Hl7v2Format(BatchFileFormat):
    """Whole-file HL7 v2 encoder/decoder backed by ``hl7``.

    PHI fields PID.5 (name), PID.7 (dob), and PID.11 (address) are
    replaced with ``"[REDACTED]"`` in decoded records.
    """

    _phi_keywords: ClassVar[frozenset[str]] = frozenset(
        {"patient_name", "date_of_birth", "address"}
    )

    # PID field indices (1-based) that carry PHI under HIPAA.
    # 3=Patient Identifier List (MRN), 5=Name, 7=DOB, 11=Address,
    # 18=Account Number, 19=SSN, 20=Driver's License.
    _phi_pid_fields: ClassVar[frozenset[int]] = frozenset({3, 5, 7, 11, 18, 19, 20})

    @property
    def name(self) -> str:
        return "hl7v2"

    async def _decode_full(
        self, payload: bytes
    ) -> Iterable[Mapping[str, Any]]:
        hl7 = self._load_hl7()
        text = payload.decode("utf-8", errors="replace")
        raw_messages = self._split_messages(text)
        records: list[dict[str, Any]] = []
        for raw in raw_messages:
            raw = raw.strip()
            if not raw:
                continue
            try:
                message = hl7.parse(raw)
            except Exception as exc:
                raise ValueError(
                    f"Hl7v2Format: failed to parse HL7 message: {exc}"
                ) from exc
            records.append(self._message_to_record(message))
        return records

    async def _encode_full(
        self, records: Iterable[Mapping[str, Any]]
    ) -> bytes:
        lines: list[str] = []
        for record in records:
            segments = record.get("segments", [])
            for seg in segments:
                seg_id = seg.get("segment_id", "")
                fields = seg.get("fields", [])
                line = seg_id + "|" + "|".join(str(f) for f in fields)
                lines.append(line)
            lines.append("")  # blank line between messages
        return "\r\n".join(lines).encode("utf-8")

    @classmethod
    def _message_to_record(cls, message: Any) -> dict[str, Any]:
        message_type = ""
        message_control_id = ""
        sending_facility = ""
        receiving_facility = ""
        segments: list[dict[str, Any]] = []

        for segment in message:
            seg_id = str(segment[0])
            fields: list[str] = []
            for i in range(1, len(segment)):
                raw_field = str(segment[i])
                if seg_id == "PID" and i in cls._phi_pid_fields:
                    fields.append("[REDACTED]")
                else:
                    fields.append(raw_field)
            segments.append({"segment_id": seg_id, "fields": fields})
            if seg_id == "MSH":
                # MSH.9 = message type, MSH.10 = control id
                # MSH.4 = sending facility, MSH.6 = receiving facility
                message_type = cls._safe_field(segment, 9)
                message_control_id = cls._safe_field(segment, 10)
                sending_facility = cls._safe_field(segment, 4)
                receiving_facility = cls._safe_field(segment, 6)

        return {
            "message_type": message_type,
            "message_control_id": message_control_id,
            "sending_facility": sending_facility,
            "receiving_facility": receiving_facility,
            "segments": segments,
        }

    @staticmethod
    def _safe_field(segment: Any, index: int) -> str:
        try:
            return str(segment[index])
        except (IndexError, KeyError):
            return ""

    @staticmethod
    def _split_messages(text: str) -> list[str]:
        """Split a multi-message HL7 text block into individual messages."""
        messages: list[str] = []
        current_lines: list[str] = []
        for line in text.splitlines():
            if line.startswith("MSH") and current_lines:
                messages.append("\r".join(current_lines))
                current_lines = [line]
            else:
                current_lines.append(line)
        if current_lines:
            messages.append("\r".join(current_lines))
        return messages

    @staticmethod
    def _load_hl7() -> Any:
        try:
            import hl7
        except ImportError as exc:
            raise ImportError(
                "Hl7v2Format requires hl7. Install with "
                "`pip install pirn[health]`."
            ) from exc
        return hl7
