"""Example: correlating agent tool spans with the run that produced them.

Wires the span plane onto a ``ParallelToolExecutor`` so every tool call emits a
span carrying the identity of the run *and* the knot it came from. Without that
correlation, agent spans arrive at a collector as an unattributable forest —
you can see that a tool was slow, but not which run to blame.

The seam is three objects, and this file exists because that assembly is not
obvious from the type names alone (PIR-830)::

    tracer   = Tracer(LoggingSink(level=logging.INFO))
    hook     = SpanEmittingToolInvocationHook(tracer, knot_id="tool_executor")
    executor = ParallelToolExecutor(..., hook=hook)

Since the ADR "agents speaks core" (WS1) a tool is a ``Knot`` class: the two
tools below declare their inputs on ``process()``, the executor constructs one
tool knot per call, and the engine runs them under the ``"tools"`` concurrency
group.  The ``hook`` input is deprecated for one cycle — each call's outcome is
its own lineage row and the run's emitters carry the same events — so this
example warns when it runs; it is kept so the span attributes stay visible.

Nothing is re-exported from a package barrel to make this shorter: pirn-agents
forbids import forwarding (enforced in CI by
``scripts/check_no_import_forwarding.py``), so every import below is the
concrete module that owns the symbol. That is the house convention, not an
oversight.

Three behaviours are worth watching in the output:

1. Every span carries ``pirn.run_id`` — read from the ambient run by ``Tracer``
   itself, so no call site has to thread it through.
2. Every tool span carries ``pirn.knot_id`` — passed in when the hook is built,
   because core has no ``_current_knot_id`` contextvar to read.
3. A span opened *outside* a run **omits** ``pirn.run_id`` rather than writing
   ``None``. A span claiming to belong to no run is worse than silence for a
   collector grouping by run id.

A fourth is visible in the attributes: calling one tool twice with equal
arguments yields the *same* ``tool.args_digest``, because the digest is keyed on
argument content rather than object identity (PIR-826).

Run with:
    uv run python examples/observability/traced_tool_calls.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Annotated, Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pydantic import Field

from pirn_agents.agent.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.observability.logging_sink import LoggingSink
from pirn_agents.observability.span_emitting_tool_invocation_hook import (
    SpanEmittingToolInvocationHook,
)
from pirn_agents.observability.tracer import Tracer
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.toolset import Toolset

EXECUTOR_KNOT_ID = "tool_executor"


# ----------------------------------------------------------------- tools


class WeatherTool(Tool):
    """Look up the current conditions for a city."""

    tool_name: ClassVar[str] = "weather"

    def __init__(self, *, city: Knot | str, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(city=city, _config=_config, **kwargs)

    async def process(
        self, city: Annotated[str, Field(description="The city to report on.")], **_: Any
    ) -> dict[str, Any]:
        """A stand-in for a real lookup — returns a canned reading."""
        await asyncio.sleep(0.01)
        return {"city": city, "temp_c": 17, "sky": "overcast"}


class FailingTool(Tool):
    """Pretends to reach a ledger service that is down."""

    tool_name: ClassVar[str] = "ledger"

    async def process(self, **_: Any) -> Any:
        """Always raises, so the example shows an ERROR span too."""
        raise RuntimeError("ledger service unreachable")


# ----------------------------------------------------------------- wiring


def build_tapestry(hook: SpanEmittingToolInvocationHook) -> Tapestry:
    """Build a one-knot tapestry whose executor reports through ``hook``."""
    calls = [
        ToolCall(tool_name="weather", arguments={"city": "Reykjavik"}, call_id="c1"),
        # Same tool, same arguments, distinct call — the digests below match,
        # which is the point of content-keyed digests.
        ToolCall(tool_name="weather", arguments={"city": "Reykjavik"}, call_id="c2"),
        ToolCall(tool_name="ledger", arguments={}, call_id="c3"),
    ]
    with Tapestry() as t:
        ParallelToolExecutor(
            tool_calls=calls,
            toolset=Toolset([WeatherTool, FailingTool]),
            max_concurrency=3,
            hook=hook,
            _config=KnotConfig(id=EXECUTOR_KNOT_ID),
        )
    return t


def _configure_logging() -> None:
    """Send the sink's records to stdout so the span attributes are visible.

    ``stream`` is set explicitly: logging defaults to stderr, which interleaves
    unpredictably with the ``print`` narration below and makes the output read
    out of order.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout, force=True)


# ----------------------------------------------------------------- main


async def main() -> None:
    _configure_logging()

    tracer = Tracer(LoggingSink(level=logging.INFO))
    hook = SpanEmittingToolInvocationHook(tracer, knot_id=EXECUTOR_KNOT_ID)

    print("\n--- a span opened OUTSIDE any run ---")
    orphan = tracer.start_span(name="startup")
    orphan.finish()
    print(
        "  pirn.run_id present?",
        "pirn.run_id" in orphan.attributes,
        "  <- omitted, not written as None",
    )

    print("\n--- three tool calls INSIDE a run ---")
    tapestry = build_tapestry(hook)
    result = await tapestry.run(RunRequest(parameters={}))

    results = result.outputs[EXECUTOR_KNOT_ID]
    print(f"\n  run_id: {result.run_id}")
    for tool_result in results:
        print(f"  {tool_result.call_id}  status={tool_result.status.value}")

    print("\n  every span above carries pirn.run_id + pirn.knot_id in attrs=...")
    print("  and the two 'weather' spans share one tool.args_digest.")


if __name__ == "__main__":
    asyncio.run(main())
