"""``ToolExecutor`` — run a single :class:`ToolCall` against the matching tool capability.

The call arrives from an upstream knot (a planner, a
:class:`~pirn_agents.planning.tool_router.ToolRouter`), so the dispatch — which
registered capability does the call name — happens in ``process()`` once the
call is resolved, and the call itself is a tool knot constructed there
(``factory.for_call(call)``) and returned as the inner pipeline's sink (ADR
agents-speaks-core, WS1).  The call therefore runs *through the engine*, under
its own id, with its own ``Result`` and lineage row in the inner run.

Its output is the :class:`ToolResult` *view* of that outcome — an
``Aggregator`` over the call knot with ``error_policy=RECEIVE_ERRORS`` builds
it through the single :meth:`ToolResult.from_result`.  A call naming an unregistered tool, or whose arguments the
declaration refuses, is a :class:`ToolCallRejection` recorded as that call's
own ``Err`` (``ToolNotFoundError`` / ``ToolArgumentValidationError``).

Algorithm:
    1. Receive the resolved ``call`` and ``tools`` (each validated into a
       :class:`ToolFactory`).
    2. Build a name-keyed registry; look up ``call.tool_name``.
    3. A match constructs ``factory.for_call(call)``; a miss or refused
       arguments construct a ``ToolCallRejection`` under the call's id.
    4. Return the view-building ``Aggregator`` as the sink.

References:
    - :class:`pirn_agents.tools.tool_factory.ToolFactory`
    - :class:`pirn_agents.tools.tool_call.ToolCall`
    - :class:`pirn_agents.tools.tool_result.ToolResult`
"""

from __future__ import annotations

import functools
from collections.abc import Sequence
from typing import Any

from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.result import Result
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.exceptions.tool_argument_validation_error import (
    ToolArgumentValidationError,
)
from pirn_agents.exceptions.tool_not_found_error import ToolNotFoundError
from pirn_agents.security.secret_redactor import SecretRedactor
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_call_rejection import ToolCallRejection
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_result import ToolResult


class ToolExecutor(SubTapestry):
    """Executes a :class:`ToolCall` against the matching tool capability, through the engine."""

    # The sink receives the call knot's ``Err`` and reports it in the view.
    _inner_failures_reach_sink = True

    def __init__(
        self,
        *,
        call: Knot,
        tools: Knot | Sequence[Any],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            call=call,
            tools=tools,
            _config=_config,
            **kwargs,
        )

    def _make_inner_tapestry(self) -> Tapestry:
        """A tapestry whose fallback ``traceback_filter`` redacts secrets."""
        return Tapestry(traceback_filter=SecretRedactor.default_traceback_filter())

    async def process(
        self,
        call: ToolCall,
        tools: Sequence[ToolFactory],
        **_: Any,
    ) -> Knot:
        """Resolve ``call`` to a capability and return the sink that runs it.

        Args:
            call: The tool call specifying the tool name, arguments, and call ID.
            tools: The registered capabilities available for dispatch.

        Returns:
            The sink of the inner pipeline: an ``Aggregator`` over the call
            knot (or a ``ToolCallRejection``) whose output — a
            :class:`ToolResult` view — becomes this knot's output.

        Raises:
            TypeError: If tools is not a sequence of tool capabilities.
            ValueError: If tools is empty.
        """
        if not isinstance(tools, Sequence) or isinstance(tools, (str, bytes)):
            raise TypeError("ToolExecutor: tools must be a sequence of tool capabilities")
        if not tools:
            raise ValueError("ToolExecutor: tools must be non-empty")
        registry = {factory.name: factory for factory in (ToolFactory.of(t) for t in tools)}
        knot_id = ToolFactory.knot_id_for(call.call_id)
        factory = registry.get(call.tool_name)
        call_knot: Knot
        if factory is None:
            call_knot = ToolCallRejection(
                call=call,
                error=ToolNotFoundError(call.tool_name, call.call_id),
                _config=KnotConfig(id=knot_id),
            )
        else:
            try:
                call_knot = factory.for_call(call)
            except ToolArgumentValidationError as exc:
                call_knot = ToolCallRejection(call=call, error=exc, _config=KnotConfig(id=knot_id))
        return Aggregator(
            combine=functools.partial(self._view, call.call_id),
            outcome=call_knot,
            _config=KnotConfig(id="outcome", error_policy=ErrorPolicy.RECEIVE_ERRORS),
        )

    @staticmethod
    def _view(call_id: str, *, outcome: Result[Any]) -> ToolResult:
        """Build the :class:`ToolResult` view from the call knot's ``Result``."""
        return ToolResult.from_result(call_id, outcome)
