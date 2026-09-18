"""``AdmissionProcessor`` — the ADT sub-pipeline.

Part of the ``examples.domain_formats.hl7v2_message_router`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_result import RunResult
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from examples.domain_formats.hl7v2_message_router.hl7_message import Hl7Message
from examples.domain_formats.hl7v2_message_router.knots import enrich_admission, parse_admission


class AdmissionProcessor(SubTapestry):
    """Inner pipeline: parse PV1 → enrich with acuity and bed data."""

    async def process(self, message: Hl7Message, **_: Any) -> RunResult:
        with Tapestry() as inner:
            p = Parameter("message", Hl7Message, default=message, _config=KnotConfig(id="msg"))
            parsed = parse_admission(message=p, _config=KnotConfig(id="parsed"))
            enrich_admission(admission=parsed, _config=KnotConfig(id="enriched"))
        return await self._run_inner(inner)
