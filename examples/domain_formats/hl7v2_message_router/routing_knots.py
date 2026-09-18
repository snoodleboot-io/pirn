"""Outer knot factories for the ``examples.domain_formats.hl7v2_message_router`` example.

These two knots make up the outer tapestry: the router that dispatches to a
``SubTapestry`` processor, and the clinical event log that reads its result.
They live apart from ``knots`` because they import the processors, and the
processors import the inner knots.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.core.run_result import RunResult
from pirn.nodes.sub_tapestry import SubTapestry

from examples.domain_formats.hl7v2_message_router.admission_processor import AdmissionProcessor
from examples.domain_formats.hl7v2_message_router.clinical_event import ClinicalEvent
from examples.domain_formats.hl7v2_message_router.hl7_message import Hl7Message
from examples.domain_formats.hl7v2_message_router.order_processor import OrderProcessor
from examples.domain_formats.hl7v2_message_router.result_processor import ResultProcessor


@KnotFactory.knot
async def route_message(message: Hl7Message) -> RunResult:
    """Dispatch to the correct SubTapestry processor by message type prefix."""
    prefix = message.message_type[:3]
    if prefix == "ADT":
        processor: SubTapestry = AdmissionProcessor(
            message=message,
            _config=KnotConfig(id="admission_processor", validate_io=False),
        )
    elif prefix == "ORM":
        processor = OrderProcessor(
            message=message,
            _config=KnotConfig(id="order_processor", validate_io=False),
        )
    elif prefix == "ORU":
        processor = ResultProcessor(
            message=message,
            _config=KnotConfig(id="result_processor", validate_io=False),
        )
    else:
        raise ValueError(
            f"unknown message type prefix: {prefix!r} (full: {message.message_type!r})"
        )
    return await processor.process(message=message)


@KnotFactory.knot
async def log_clinical_event(message: Hl7Message, routed_result: RunResult) -> dict[str, Any]:
    """Extract the ClinicalEvent from the routed result and create a log entry."""
    output_key = {
        "ADT": "enriched",
        "ORM": "validated",
        "ORU": "interpreted",
    }.get(message.message_type[:3], "")

    event: ClinicalEvent | None = routed_result.outputs.get(output_key)
    if event is None:
        return {
            "encounter_id": message.encounter_id,
            "message_type": message.message_type,
            "status": "routing_error",
            "requires_alert": False,
        }

    return {
        "encounter_id": event.encounter_id,
        "message_type": message.message_type,
        "event_kind": event.event_kind,
        "requires_alert": event.requires_alert,
        "details": event.details,
    }
