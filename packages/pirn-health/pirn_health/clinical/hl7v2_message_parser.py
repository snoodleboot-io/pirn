"""``HL7v2MessageParser`` — parse a raw HL7v2 string into a clinical record.

Production version would use ``hl7apy`` or ``python-hl7`` to parse the
pipe-delimited segments. This stub validates the message string is
non-empty and returns a deterministic :class:`ClinicalRecord` derived
from a few easily-recovered fields.

Algorithm:
    1. Receive a message string and a hashing salt.
    2. Validate that message and salt are non-empty strings.
    3. Parse the MSH/PID/PV1/OBX segments.
    4. Hash PID-3 (the patient identifier) and the encounter identifier with
       :class:`~pirn_health.clinical.phi_hasher.PhiHasher`, the same salted scheme
       :class:`~pirn_health.assemblers.fhir_patient_assembler.FhirPatientAssembler`
       uses, so no raw identifier ever reaches a :class:`ClinicalRecord`.
    5. Parse MSH-7 into ``observed_at``, raising when it is absent or malformed —
       an unreadable message timestamp is an error, not a reason to stamp the
       record with the current time.
    6. Construct and return a ClinicalRecord from the parsed fields.

PHI safety:
    The raw PID-3 value exists only inside :meth:`process`; what leaves the knot
    is the salted token. A message with no patient identifier cannot produce a
    patient record and is rejected.

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

from datetime import UTC, datetime, timedelta, timezone
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.clinical.phi_hasher import PhiHasher
from pirn_health.types.clinical_record import ClinicalRecord


class HL7v2MessageParser(Knot):
    """Parse one HL7v2 message into a :class:`ClinicalRecord`."""

    _is_stub: ClassVar[bool] = True

    def __init__(
        self,
        *,
        message: Knot | str,
        salt: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, salt=salt, _config=_config, **kwargs)

    async def process(
        self,
        message: str,
        salt: str,
        **_: Any,
    ) -> ClinicalRecord:
        """Parse the HL7v2 message segments and return a ClinicalRecord.

        Args:
            message: Non-empty HL7v2 message string to parse.
            salt: Non-empty string used to hash the patient and encounter identifiers,
                the same salt :class:`PHIRedactor` is configured with.

        Returns:
            A ClinicalRecord whose identifiers are salted tokens, never the raw
            PID-3 value.

        Raises:
            TypeError: If message or salt is not a string.
            ValueError: If message or salt is empty, the message carries no patient
                identifier, or MSH-7 is missing or unparseable.
        """
        if not isinstance(message, str):
            raise TypeError("HL7v2MessageParser: message must be a string")
        if not message:
            raise ValueError("HL7v2MessageParser: message must be non-empty")
        if not isinstance(salt, str):
            raise TypeError("HL7v2MessageParser: salt must be a string")
        if not salt:
            raise ValueError("HL7v2MessageParser: salt must be non-empty")

        segments: dict[str, list[list[str]]] = {}
        for line in message.splitlines():
            line = line.strip()
            if not line:
                continue
            fields = line.split("|")
            seg_name = fields[0].upper()
            segments.setdefault(seg_name, []).append(fields)

        # PID-3: patient identifier list; PID-2 fallback. The raw value is PHI and
        # never leaves this method — only its salted token does.
        raw_patient_id = self._field(segments, "PID", 3) or self._field(segments, "PID", 2)
        if not raw_patient_id:
            raise ValueError(
                "HL7v2MessageParser: message carries no patient identifier (PID-3/PID-2) — "
                "it cannot be parsed into a ClinicalRecord"
            )
        # PV1-19: visit number as encounter ID; MSH-10 (message control ID) as fallback
        raw_encounter_id = self._field(segments, "PV1", 19) or self._field(segments, "MSH", 10)

        # OBX-3: observation identifier (component 0 = code, component 2 = display)
        observation_codes = tuple(
            self._field(segments, "OBX", 3, component=0, occurrence=i)
            for i in range(len(segments.get("OBX", [])))
            if self._field(segments, "OBX", 3, component=0, occurrence=i)
        )

        observed_at = self._message_datetime(self._field(segments, "MSH", 7))

        return ClinicalRecord(
            patient_id=PhiHasher.hash_identifier(salt, raw_patient_id),
            encounter_id=PhiHasher.hash_identifier(salt, raw_encounter_id),
            observation_codes=observation_codes,
            observed_at=observed_at,
            source_system="hl7v2",
        )

    @staticmethod
    def _message_datetime(dt_raw: str) -> datetime:
        """Parse an HL7 DTM (MSH-7) into an aware datetime.

        The DTM is ``YYYY[MM[DD[HH[MM[SS]]]]][.S[S[S[S]]]][+/-ZZZZ]``. A message
        with no MSH-7, or one whose MSH-7 does not parse, raises: substituting
        ``datetime.now()`` would stamp every malformed message with the moment
        it happened to be ingested and make that fabrication indistinguishable
        from a real timestamp.

        Args:
            dt_raw: The raw MSH-7 field value.

        Returns:
            The timezone-aware message timestamp (UTC when the DTM carries no offset).

        Raises:
            ValueError: If ``dt_raw`` is empty or not a valid HL7 DTM.
        """
        if not dt_raw:
            raise ValueError("HL7v2MessageParser: MSH-7 (message date/time) is missing")
        stamp = dt_raw
        tzinfo: timezone = UTC
        if len(stamp) > 5 and stamp[-5] in "+-":
            sign = 1 if stamp[-5] == "+" else -1
            offset, stamp = stamp[-4:], stamp[:-5]
            try:
                tzinfo = timezone(sign * timedelta(hours=int(offset[:2]), minutes=int(offset[2:])))
            except ValueError as exc:
                raise ValueError(
                    f"HL7v2MessageParser: MSH-7 has a malformed UTC offset: {dt_raw!r}"
                ) from exc
        stamp = stamp.split(".", 1)[0]
        formats = {14: "%Y%m%d%H%M%S", 12: "%Y%m%d%H%M", 10: "%Y%m%d%H", 8: "%Y%m%d"}
        fmt = formats.get(len(stamp))
        if fmt is None:
            raise ValueError(f"HL7v2MessageParser: MSH-7 is not a valid HL7 date/time: {dt_raw!r}")
        try:
            return datetime.strptime(stamp, fmt).replace(tzinfo=tzinfo)
        except ValueError as exc:
            raise ValueError(
                f"HL7v2MessageParser: MSH-7 is not a valid HL7 date/time: {dt_raw!r}"
            ) from exc

    @staticmethod
    def _field(
        segments: dict[str, list[list[str]]],
        seg: str,
        field_idx: int,
        component: int = 0,
        occurrence: int = 0,
    ) -> str:
        """Return one component of one field of one segment occurrence, or ``""``.

        ``field_idx`` is the HL7 field number (PID-3 is ``3``). MSH is the one
        segment whose numbering is offset: MSH-1 *is* the field separator, so
        splitting the line on it leaves MSH-n at list index ``n - 1`` — reading
        MSH-7 at index 7 returns MSH-8 (the security field), which is empty in
        every real message.
        """
        rows = segments.get(seg, [])
        if occurrence >= len(rows):
            return ""
        fields = rows[occurrence]
        index = field_idx - 1 if seg == "MSH" else field_idx
        if index >= len(fields):
            return ""
        components = fields[index].split("^")
        return components[component].strip() if component < len(components) else ""
