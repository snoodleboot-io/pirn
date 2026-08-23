"""``SpecialistInvocation`` — run one delegated specialist as a graph node.

A single-specialist knot: it invokes exactly one specialist (a
:class:`~pirn.nodes.sub_tapestry.SubTapestry`) through the engine entry point
(:func:`invoke_specialist`, i.e. the specialist's ``__call__`` — never its
``process()``; see PIR-769) and returns that specialist's answer normalised to
an :class:`AgentResponse`.

Wiring N of these as the parents of a single
:class:`~pirn.nodes.aggregator.Aggregator` lets the *engine* schedule the whole
fan-out wave concurrently (the scheduler runs every ready sibling in one
``asyncio.gather``) instead of the caller doing its own ``asyncio.gather`` over
``process()`` outside the engine. See PIR-714.

The specialist is held on a ``_mutable_`` slot rather than passed to
``super().__init__``. Two facts from ``pirn.core.knot`` force this:

* a ``Knot``-valued constructor kwarg is partitioned into the knot's *parents*
  and resolved as an *input* by the engine — but the specialist is opaque data
  this knot invokes itself, not an upstream value to resolve; and
* the post-freeze ``__setattr__`` guard blocks injecting the specialist after
  construction unless the attribute name is ``_mutable_``-prefixed.

Holding it as ``_mutable_`` state therefore mirrors core's own ``_mutable_``
idiom (see :class:`~pirn.nodes.sub_tapestry.SubTapestry`) and keeps the existing
``StubSpecialist`` / ``StubDebater`` test doubles valid without a factory
contract (that factory question is PIR-759's, out of scope here).

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.specializations.multi_agent._specialist_invoker import (
    invoke_specialist,
)
from pirn_agents.types.messaging.agent_response import AgentResponse


class SpecialistInvocation(Knot):
    """Invoke one specialist and surface its :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        specialist: SubTapestry,
        task: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(task=task, _config=_config, **kwargs)
        # Held as _mutable_ data, NOT passed to super(): a Knot-valued kwarg
        # would be registered as a parent and resolved as an input, and the
        # freeze guard blocks a plain post-construction assignment. See the
        # module docstring.
        object.__setattr__(self, "_mutable_specialist", specialist)

    async def process(self, task: str, **_: Any) -> AgentResponse:
        """Run the held specialist on ``task`` and return its normalised response.

        Args:
            task: The task string handed to the specialist (already framed by an
                upstream knot when the caller needs runtime framing).

        Returns:
            The specialist's :class:`AgentResponse`; a non-response result is
            wrapped in one with ``finish_reason="stop"``, exactly as the old
            fan-out sites normalised their gathered results.
        """
        raw = await invoke_specialist(self._mutable_specialist, task=task)
        if isinstance(raw, AgentResponse):
            return raw
        return AgentResponse(content=str(raw), finish_reason="stop")
