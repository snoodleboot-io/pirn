"""Example: HL7v2 message routing with SubTapestry nodes (single-file).

Demonstrates the SubTapestry pattern applied to healthcare data.  An
integration engine receives a stream of HL7v2 messages; each message is
routed to a specialist sub-pipeline based on its type, then all results
feed a central clinical event log.

Topology:

    message ──► MessageRouter ──► AdmissionProcessor (ADT^A01/A03)  ──► ClinicalEventLog
                             ──► OrderProcessor     (ORM^O01)       ──► ClinicalEventLog
                             ──► ResultProcessor    (ORU^R01)       ──► ClinicalEventLog

Each sub-pipeline is a SubTapestry subclass with its own inner execution
graph.  The outer tapestry contains only three high-level nodes:
MessageRouter, and ClinicalEventLog; routing logic stays inside
MessageRouter.process().

Working with real HL7v2 data
-----------------------------
Replace _synthetic_messages() with a live feed from your HL7 broker or
MLLP listener.  The Hl7v2Format.decode() method returns dicts matching
the Hl7Message.segments schema used here.  Segment field indices follow
the HL7 v2.x standard (PV1.3 = assigned patient location, OBR.4 =
universal service identifier, OBX.5 = observation value, etc.).

Run with:
    uv run python examples/domain_formats/hl7v2_message_router.py
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.nodes.branch.branch import Branch
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

# ----------------------------------------------------------------- models


@dataclass
class Hl7Message:
    message_type: str
    segments: list[dict[str, Any]]
    encounter_id: str


@dataclass
class AdmissionEvent:
    encounter_id: str
    event_type: str  # "admission" / "discharge"
    department: str
    acuity: str
    bed_id: str


@dataclass
class ClinicalOrder:
    encounter_id: str
    order_id: str
    order_type: str
    priority: str
    ordered_by: str
    test_codes: list[str]


@dataclass
class LabResult:
    encounter_id: str
    order_id: str
    test_code: str
    value: str
    unit: str
    reference_range: str
    flag: str  # "H" / "L" / "N" / "C"


@dataclass
class ClinicalEvent:
    encounter_id: str
    event_kind: str
    details: dict[str, Any]
    requires_alert: bool


# ----------------------------------------------------------------- inner knots — admission


@KnotFactory.knot
async def parse_admission(message: Hl7Message) -> AdmissionEvent:
    """Extract PV1 segment fields into an AdmissionEvent."""
    pv1 = next(
        (s for s in message.segments if s["segment_id"] == "PV1"),
        None,
    )
    fields: list[str] = pv1["fields"] if pv1 else []

    def _get(idx: int, default: str = "") -> str:
        return fields[idx] if idx < len(fields) else default

    event_type = "discharge" if message.message_type.endswith("A03") else "admission"
    return AdmissionEvent(
        encounter_id=message.encounter_id,
        event_type=event_type,
        department=_get(3, "UNKNOWN"),
        acuity="",
        bed_id=_get(2, "UNASSIGNED"),
    )


@KnotFactory.knot
async def enrich_admission(admission: AdmissionEvent) -> ClinicalEvent:
    """Assign acuity score and check bed availability."""
    dept_acuity = {
        "ED": "EMERGENT",
        "ICU": "CRITICAL",
        "MED-SURG": "STABLE",
        "OB": "MODERATE",
    }
    acuity = dept_acuity.get(admission.department, "STABLE")
    admission.acuity = acuity
    requires_alert = acuity in ("EMERGENT", "CRITICAL")
    return ClinicalEvent(
        encounter_id=admission.encounter_id,
        event_kind=admission.event_type,
        details={
            "department": admission.department,
            "acuity": acuity,
            "bed_id": admission.bed_id,
        },
        requires_alert=requires_alert,
    )


# ----------------------------------------------------------------- inner knots — orders


@KnotFactory.knot
async def parse_order(message: Hl7Message) -> ClinicalOrder:
    """Extract OBR segment fields into a ClinicalOrder."""
    obr = next(
        (s for s in message.segments if s["segment_id"] == "OBR"),
        None,
    )
    fields: list[str] = obr["fields"] if obr else []

    def _get(idx: int, default: str = "") -> str:
        return fields[idx] if idx < len(fields) else default

    test_codes = [c.strip() for c in _get(4, "").split("^") if c.strip()]
    return ClinicalOrder(
        encounter_id=message.encounter_id,
        order_id=_get(2, f"ORD-{message.encounter_id}"),
        order_type=_get(24, "LAB"),
        priority=_get(27, "R"),
        ordered_by=_get(16, "SYSTEM"),
        test_codes=test_codes or ["UNKNOWN"],
    )


@KnotFactory.knot
async def validate_order(order: ClinicalOrder) -> ClinicalEvent:
    """Check order completeness and confirm priority."""
    is_stat = order.priority in ("S", "STAT")
    complete = bool(order.order_id and order.test_codes and order.ordered_by != "SYSTEM")
    details: dict[str, Any] = {
        "order_id": order.order_id,
        "order_type": order.order_type,
        "priority": order.priority,
        "ordered_by": order.ordered_by,
        "test_codes": order.test_codes,
        "complete": complete,
    }
    return ClinicalEvent(
        encounter_id=order.encounter_id,
        event_kind="order",
        details=details,
        requires_alert=is_stat,
    )


# ----------------------------------------------------------------- inner knots — results


@KnotFactory.knot
async def parse_results(message: Hl7Message) -> list[LabResult]:
    """Extract all OBX segments into LabResult records."""
    obx_segments = [s for s in message.segments if s["segment_id"] == "OBX"]
    obr = next(
        (s for s in message.segments if s["segment_id"] == "OBR"),
        None,
    )
    order_id = obr["fields"][2] if obr and len(obr["fields"]) > 2 else f"ORD-{message.encounter_id}"

    results: list[LabResult] = []
    for seg in obx_segments:
        f = seg["fields"]

        def _get(idx: int, default: str = "", *, _f: list = f) -> str:
            return _f[idx] if idx < len(_f) else default

        results.append(
            LabResult(
                encounter_id=message.encounter_id,
                order_id=order_id,
                test_code=_get(3, "UNKNOWN"),
                value=_get(5, ""),
                unit=_get(6, ""),
                reference_range=_get(7, ""),
                flag=_get(8, "N"),
            )
        )
    return results


@KnotFactory.knot
async def interpret_results(results: list[LabResult]) -> ClinicalEvent:
    """Flag critical values and build a ClinicalEvent."""
    critical = [r for r in results if r.flag in ("H", "L", "C")]
    requires_alert = len(critical) > 0
    encounter_id = results[0].encounter_id if results else "UNKNOWN"
    details: dict[str, Any] = {
        "result_count": len(results),
        "critical_count": len(critical),
        "flags": {r.test_code: r.flag for r in results},
        "critical_tests": [r.test_code for r in critical],
    }
    return ClinicalEvent(
        encounter_id=encounter_id,
        event_kind="result",
        details=details,
        requires_alert=requires_alert,
    )


# ----------------------------------------------------------------- SubTapestry nodes


# ``process`` returns the terminal knot of the inner graph and the framework
# runs it: the base ``__call__`` establishes the inner tapestry context, invokes
# ``process``, runs the inner graph and surfaces the sink's output as this
# knot's output. Building a ``Tapestry`` by hand and calling ``_run_inner``
# would run the inner graph outside the engine, so the outer run would record
# no lineage for any of these knots.


class AdmissionProcessor(SubTapestry):
    """Inner pipeline: parse PV1 → enrich with acuity and bed data."""

    async def process(self, message: Hl7Message, **_: Any) -> Knot:
        p = Parameter("message", Hl7Message, default=message, _config=KnotConfig(id="msg"))
        parsed = parse_admission(message=p, _config=KnotConfig(id="parsed"))
        return enrich_admission(admission=parsed, _config=KnotConfig(id="enriched"))


class OrderProcessor(SubTapestry):
    """Inner pipeline: parse OBR → validate order completeness."""

    async def process(self, message: Hl7Message, **_: Any) -> Knot:
        p = Parameter("message", Hl7Message, default=message, _config=KnotConfig(id="msg"))
        parsed = parse_order(message=p, _config=KnotConfig(id="parsed"))
        return validate_order(order=parsed, _config=KnotConfig(id="validated"))


class ResultProcessor(SubTapestry):
    """Inner pipeline: parse OBX segments → interpret critical values."""

    async def process(self, message: Hl7Message, **_: Any) -> Knot:
        p = Parameter("message", Hl7Message, default=message, _config=KnotConfig(id="msg"))
        parsed = parse_results(message=p, _config=KnotConfig(id="parsed"))
        return interpret_results(results=parsed, _config=KnotConfig(id="interpreted"))


# ----------------------------------------------------------------- outer knots


# Dispatch is a ``Branch``: one selector reads the message-type prefix and the
# non-selected branches come back ``Skipped`` with reason "branch_not_selected",
# so the processors downstream of them never run. The previous shape built a
# processor inside a plain knot and awaited ``processor.process(...)`` by hand,
# which ran a whole inner pipeline outside the engine -- no scheduling, no
# lineage, and a return type the base class does not declare.

_PREFIX_PROCESSORS: dict[str, type[SubTapestry]] = {
    "ADT": AdmissionProcessor,
    "ORM": OrderProcessor,
    "ORU": ResultProcessor,
}


def _message_prefix(message: Hl7Message) -> str:
    """Select the branch for ``message``; raises on an unroutable type."""
    prefix = message.message_type[:3]
    if prefix not in _PREFIX_PROCESSORS:
        raise ValueError(
            f"unknown message type prefix: {prefix!r} (full: {message.message_type!r})"
        )
    return prefix


@KnotFactory.knot
async def log_clinical_event(message: Hl7Message, event: ClinicalEvent) -> dict[str, Any]:
    """Create a log entry from the routed processor's clinical event."""
    return {
        "encounter_id": event.encounter_id,
        "message_type": message.message_type,
        "event_kind": event.event_kind,
        "requires_alert": event.requires_alert,
        "details": event.details,
    }


# ----------------------------------------------------------------- synthetic data


def _synthetic_messages() -> list[Hl7Message]:
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


# ----------------------------------------------------------------- wiring


#: One ``event_log`` knot per branch. Exactly one runs per message; the other
#: two are skipped because their processor was skipped, so a run surfaces a
#: single entry under the selected branch's key.
EVENT_LOG_IDS: tuple[str, ...] = tuple(
    f"event_log_{prefix.lower()}" for prefix in _PREFIX_PROCESSORS
)


def build_tapestry(history=None) -> Tapestry:
    with Tapestry(history=history) as t:
        message = Parameter("message", Hl7Message, _config=KnotConfig(id="message"))
        route = Branch(
            input=message,
            selector=_message_prefix,
            branches=tuple(_PREFIX_PROCESSORS),
            _config=KnotConfig(id="route", validate_io=False),
        )
        for prefix, processor_class in _PREFIX_PROCESSORS.items():
            key = prefix.lower()
            processed = processor_class(
                message=route[prefix],
                _config=KnotConfig(id=f"{key}_processor", validate_io=False),
            )
            log_clinical_event(
                message=message,
                event=processed,
                _config=KnotConfig(id=f"event_log_{key}", validate_io=False),
            )
    return t


# ----------------------------------------------------------------- main


async def main() -> None:
    history = SQLiteHistory(path=str(Path(__file__).parent.parent / "pirn.db"))
    tapestry = build_tapestry(history=history)
    messages = _synthetic_messages()

    print(f"Processing {len(messages)} HL7v2 messages\n")
    print(f"{'ENC':>10}  {'TYPE':<12}  {'KIND':<12}  {'ALERT':<6}  DETAILS")
    print("-" * 80)

    for msg in messages:
        result = await tapestry.run(RunRequest(parameters={"message": msg}))
        if not result.succeeded:
            exc_info = result.exceptions[0] if result.exceptions else None
            err_msg = exc_info.message[:60] if exc_info else "unknown error"
            err_line = (
                f"{msg.encounter_id:>10}  {msg.message_type:<12}  {'ERROR':<12}  {'':6}  {err_msg}"
            )
            print(err_line)
            continue

        # Exactly one branch ran, so exactly one of the three log knots
        # produced an entry; the rest were skipped and are absent.
        log_entry: dict[str, Any] = next(
            (result.outputs[k] for k in EVENT_LOG_IDS if result.outputs.get(k)), {}
        )
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


if __name__ == "__main__":
    asyncio.run(main())
