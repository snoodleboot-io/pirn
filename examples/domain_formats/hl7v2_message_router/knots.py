"""Inner knot factories for the ``examples.domain_formats.hl7v2_message_router`` example.

These are the segment-level knots the three ``SubTapestry`` processors wire into
their inner graphs. The two outer knots live in ``routing_knots``, which imports
the processors that import this module.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_factory import KnotFactory

from examples.domain_formats.hl7v2_message_router.admission_event import AdmissionEvent
from examples.domain_formats.hl7v2_message_router.clinical_event import ClinicalEvent
from examples.domain_formats.hl7v2_message_router.clinical_order import ClinicalOrder
from examples.domain_formats.hl7v2_message_router.hl7_message import Hl7Message
from examples.domain_formats.hl7v2_message_router.hl7_segment import Hl7Segment
from examples.domain_formats.hl7v2_message_router.lab_result import LabResult


@KnotFactory.knot
async def parse_admission(message: Hl7Message) -> AdmissionEvent:
    """Extract PV1 segment fields into an AdmissionEvent."""
    fields = Hl7Segment.fields_of(message.segments, "PV1")

    event_type = "discharge" if message.message_type.endswith("A03") else "admission"
    return AdmissionEvent(
        encounter_id=message.encounter_id,
        event_type=event_type,
        department=Hl7Segment.field(fields, 3, "UNKNOWN"),
        acuity="",
        bed_id=Hl7Segment.field(fields, 2, "UNASSIGNED"),
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


@KnotFactory.knot
async def parse_order(message: Hl7Message) -> ClinicalOrder:
    """Extract OBR segment fields into a ClinicalOrder."""
    fields = Hl7Segment.fields_of(message.segments, "OBR")

    test_codes = [c.strip() for c in Hl7Segment.field(fields, 4).split("^") if c.strip()]
    return ClinicalOrder(
        encounter_id=message.encounter_id,
        order_id=Hl7Segment.field(fields, 2, f"ORD-{message.encounter_id}"),
        order_type=Hl7Segment.field(fields, 24, "LAB"),
        priority=Hl7Segment.field(fields, 27, "R"),
        ordered_by=Hl7Segment.field(fields, 16, "SYSTEM"),
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


@KnotFactory.knot
async def parse_results(message: Hl7Message) -> list[LabResult]:
    """Extract all OBX segments into LabResult records."""
    obx_segments = [s for s in message.segments if s["segment_id"] == "OBX"]
    obr_fields = Hl7Segment.fields_of(message.segments, "OBR")
    order_id = obr_fields[2] if len(obr_fields) > 2 else f"ORD-{message.encounter_id}"

    results: list[LabResult] = []
    for seg in obx_segments:
        fields = seg["fields"]
        results.append(
            LabResult(
                encounter_id=message.encounter_id,
                order_id=order_id,
                test_code=Hl7Segment.field(fields, 3, "UNKNOWN"),
                value=Hl7Segment.field(fields, 5),
                unit=Hl7Segment.field(fields, 6),
                reference_range=Hl7Segment.field(fields, 7),
                flag=Hl7Segment.field(fields, 8, "N"),
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
