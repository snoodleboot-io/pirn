"""Example: HL7v2 message routing with SubTapestry nodes.

Demonstrates the SubTapestry pattern applied to healthcare data.  An
integration engine receives a stream of HL7v2 messages; each message is
routed to a specialist sub-pipeline based on its type, then all results
feed a central clinical event log.

Topology:

    message ──► MessageRouter ──► AdmissionProcessor (ADT^A01/A03)  ──► ClinicalEventLog
                             ──► OrderProcessor     (ORM^O01)       ──► ClinicalEventLog
                             ──► ResultProcessor    (ORU^R01)       ──► ClinicalEventLog

Each sub-pipeline is a SubTapestry subclass with its own inner execution
graph.  The outer tapestry contains only two high-level nodes: the router
and the clinical event log; routing logic stays inside ``route_message``.

Working with real HL7v2 data
-----------------------------
Replace ``Hl7v2MessageRouter._synthetic_messages()`` with a live feed from
your HL7 broker or MLLP listener.  The Hl7v2Format.decode() method returns
dicts matching the Hl7Message.segments schema used here.  Segment field
indices follow the HL7 v2.x standard (PV1.3 = assigned patient location,
OBR.4 = universal service identifier, OBX.5 = observation value, etc.).

Run with:
    uv run python -m examples.domain_formats.hl7v2_message_router
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from examples.domain_formats.hl7v2_message_router.hl7_message import Hl7Message
from examples.domain_formats.hl7v2_message_router.routing_knots import (
    log_clinical_event,
    route_message,
)


class Hl7v2MessageRouter:
    """Builds and runs the outer routing tapestry over a batch of HL7v2 messages."""

    @staticmethod
    def build_tapestry(history: SQLiteHistory | None = None) -> Tapestry:
        """Wire message → route_message → log_clinical_event."""
        with Tapestry(history=history) as t:
            message = Parameter("message", Hl7Message, _config=KnotConfig(id="message"))
            routed = route_message(
                message=message,
                _config=KnotConfig(id="router", validate_io=False),
            )
            log_clinical_event(
                message=message,
                routed_result=routed,
                _config=KnotConfig(id="event_log", validate_io=False),
            )
        return t

    @staticmethod
    def _synthetic_messages() -> list[Hl7Message]:
        """Build a deterministic batch of three ADT, two ORM and three ORU messages."""
        rng = random.Random(42)
        departments = ["ED", "ICU", "MED-SURG", "OB"]
        beds = ["A101", "B204", "C312", "ICU-05", "ED-07"]
        providers = ["DR.SMITH", "DR.JONES", "DR.PATEL", "DR.CHEN"]
        test_codes = ["CBC", "BMP", "TROPONIN", "PT", "LIPASE", "TSH", "HBA1C"]
        flags_pool = ["N", "N", "N", "H", "L", "C"]

        messages: list[Hl7Message] = []

        # Three ADT messages (admissions and one discharge)
        for i, (msg_type, label) in enumerate(
            [("ADT^A01", "admission"), ("ADT^A01", "admission"), ("ADT^A03", "discharge")]
        ):
            enc = f"ENC-{i:04d}"
            dept = rng.choice(departments)
            bed = rng.choice(beds)
            segments = [
                {
                    "segment_id": "MSH",
                    "fields": [
                        "^~\\&",
                        "SENDING_APP",
                        "SENDING_FAC",
                        "RECV_APP",
                        "RECV_FAC",
                        "20260502120000",
                        "",
                        msg_type,
                        f"MSG{i:06d}",
                        "P",
                        "2.5",
                    ],
                },
                {
                    "segment_id": "PID",
                    "fields": [
                        "1",
                        enc,
                        enc,
                        "",
                        f"DOE^PATIENT{i}",
                        "",
                        "19800101",
                        rng.choice(["M", "F"]),
                    ],
                },
                {
                    "segment_id": "PV1",
                    "fields": [
                        "1",
                        "I" if label == "admission" else "D",
                        bed,
                        "",
                        "",
                        "",
                        rng.choice(providers),
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        enc,
                        dept,
                    ],
                },
            ]
            messages.append(Hl7Message(message_type=msg_type, segments=segments, encounter_id=enc))

        # Two ORM messages
        for i in range(2):
            enc = f"ENC-{i + 3:04d}"
            codes = rng.sample(test_codes, k=rng.randint(1, 3))
            priority = rng.choice(["R", "S", "R"])
            segments = [
                {
                    "segment_id": "MSH",
                    "fields": [
                        "^~\\&",
                        "CPOE",
                        "HOSPITAL",
                        "LAB",
                        "HOSPITAL",
                        "20260502130000",
                        "",
                        "ORM^O01",
                        f"MSG{i + 3:06d}",
                        "P",
                        "2.5",
                    ],
                },
                {
                    "segment_id": "PID",
                    "fields": ["1", enc, enc, "", f"DOE^PATIENT{i + 3}"],
                },
                {
                    "segment_id": "OBR",
                    "fields": [
                        "1",
                        f"PLACER-{enc}",
                        f"ORD-{enc}",
                        "^".join(codes),
                        "",
                        "20260502130000",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        rng.choice(providers),
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "LAB",
                        "",
                        "",
                        priority,
                    ],
                },
            ]
            messages.append(Hl7Message(message_type="ORM^O01", segments=segments, encounter_id=enc))

        # Three ORU messages
        for i in range(3):
            enc = f"ENC-{i + 5:04d}"
            num_obx = rng.randint(2, 4)
            segments = [
                {
                    "segment_id": "MSH",
                    "fields": [
                        "^~\\&",
                        "LIS",
                        "LAB",
                        "CPOE",
                        "HOSPITAL",
                        "20260502140000",
                        "",
                        "ORU^R01",
                        f"MSG{i + 5:06d}",
                        "P",
                        "2.5",
                    ],
                },
                {
                    "segment_id": "PID",
                    "fields": ["1", enc, enc, "", f"DOE^PATIENT{i + 5}"],
                },
                {
                    "segment_id": "OBR",
                    "fields": [
                        "1",
                        f"PLACER-{enc}",
                        f"ORD-{enc}",
                        rng.choice(test_codes),
                    ],
                },
            ]
            for j in range(num_obx):
                code = rng.choice(test_codes)
                val = str(round(rng.uniform(0.5, 200.0), 1))
                flag = rng.choice(flags_pool)
                segments.append(
                    {
                        "segment_id": "OBX",
                        "fields": [
                            str(j + 1),
                            "NM",
                            "",
                            code,
                            "",
                            val,
                            "mg/dL",
                            "0.5-200.0",
                            flag,
                        ],
                    }
                )
            messages.append(Hl7Message(message_type="ORU^R01", segments=segments, encounter_id=enc))

        return messages

    @classmethod
    async def main(cls) -> None:
        """Route every synthetic message and print the resulting clinical event log."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))
        tapestry = cls.build_tapestry(history=history)
        messages = cls._synthetic_messages()

        print(f"Processing {len(messages)} HL7v2 messages\n")
        print(f"{'ENC':>10}  {'TYPE':<12}  {'KIND':<12}  {'ALERT':<6}  DETAILS")
        print("-" * 80)

        for msg in messages:
            result = await tapestry.run(RunRequest(parameters={"message": msg}))
            if not result.succeeded:
                exc_info = result.exceptions[0] if result.exceptions else None
                err_msg = exc_info.message[:60] if exc_info else "unknown error"
                err_line = (
                    f"{msg.encounter_id:>10}  {msg.message_type:<12}  "
                    f"{'ERROR':<12}  {'':6}  {err_msg}"
                )
                print(err_line)
                continue

            log_entry: dict[str, Any] = result.outputs.get("event_log", {})
            enc = log_entry.get("encounter_id", msg.encounter_id)
            kind = log_entry.get("event_kind", "?")
            alert = "YES" if log_entry.get("requires_alert") else "no"
            details = log_entry.get("details", {})

            if kind == "admission" or kind == "discharge":
                brief = (
                    f"dept={details.get('department')} acuity={details.get('acuity')}"
                    f" bed={details.get('bed_id')}"
                )
            elif kind == "order":
                brief = (
                    f"order_id={details.get('order_id')} codes={details.get('test_codes')}"
                    f" priority={details.get('priority')}"
                )
            elif kind == "result":
                brief = (
                    f"results={details.get('result_count')}"
                    f" critical={details.get('critical_count')} flags={details.get('flags')}"
                )
            else:
                brief = str(details)[:60]

            print(f"{enc:>10}  {msg.message_type:<12}  {kind:<12}  {alert:<6}  {brief}")

        print("-" * 80)
        print("Done.")
