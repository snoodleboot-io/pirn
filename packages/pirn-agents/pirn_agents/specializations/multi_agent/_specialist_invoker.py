"""Invoke a delegated specialist through the engine entry point, not ``process()``.

Four multi-agent pipelines delegate to specialists that are themselves
``SubTapestry`` instances. Each of them used to ``await specialist.process(...)``
directly. That is not the contract: ``process()`` *builds and returns the sink
knot* of the specialist's inner pipeline — it does not run it. Only
``__call__`` establishes the inner tapestry, runs the graph and extracts the
sink's output.

Calling ``process()`` therefore handed the caller a ``Knot`` where an answer was
expected. Because every one of those callers guarded with
``isinstance(raw, AgentResponse)``, the ``Knot`` failed the guard and was either
stringified into the answer or silently dropped — with the run still reporting
success. See PIR-769.
"""

from __future__ import annotations

from typing import Any

from pirn.core.ok import Ok
from pirn.core.skipped import Skipped
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.specializations.multi_agent.specialist_invocation_error import (
    SpecialistInvocationError,
)


async def invoke_specialist(specialist: SubTapestry, **inputs: Any) -> Any:
    """Run ``specialist`` to completion and return the value it produced.

    Args:
        specialist: The specialist pipeline to delegate to.
        **inputs: Inputs to supply to the specialist, overriding the values it
            was constructed with. These reach ``process()`` as keyword
            arguments, exactly as the engine would supply parent results.

    Returns:
        The specialist's output — the value its sink knot produced.

    Raises:
        SpecialistInvocationError: If the specialist failed or was skipped.
            Neither outcome carries a value, so there is nothing to return and
            the caller must not proceed as though there were.
    """
    result = await specialist(inputs)
    if isinstance(result, Ok):
        return result.value
    if isinstance(result, Skipped):
        raise SpecialistInvocationError(specialist.knot_id, f"skipped ({result.reason})")
    raise SpecialistInvocationError(
        specialist.knot_id,
        f"{result.record.exc_type}: {result.record.message}",
    )
