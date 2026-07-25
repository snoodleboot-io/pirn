"""``ObservabilitySink`` — the pluggable, no-op-by-default span destination."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pirn_agents.observability.span import Span


class ObservabilitySink:
    """Receives span lifecycle callbacks; the base class is a genuine no-op.

    Mirrors the design of F1's
    :class:`~pirn_agents.tool_invocation_hook.ToolInvocationHook`: the three
    methods return ``None`` and do nothing, so a :class:`Tracer` wired with the
    base sink (or none at all) does zero observability work — the default is
    *behaviour*, not a placeholder. Subclasses override the callbacks to log,
    export to OTel, or emit metrics; those overrides must stay side-effect-free
    on the traced path (a raising sink must never alter control flow — the
    tracer swallows sink exceptions).

    Contract
    --------
    * :meth:`on_start` fires once, when a span opens.
    * :meth:`on_event` fires zero or more times between start and finish.
    * :meth:`on_finish` fires exactly once, for every terminal outcome.
    """

    def on_start(self, span: Span) -> None:
        """Signal that ``span`` has opened. Base implementation: no-op."""
        return None

    def on_event(self, span: Span, name: str, attributes: Mapping[str, Any]) -> None:
        """Signal a named event within ``span``. Base implementation: no-op."""
        return None

    def on_finish(self, span: Span) -> None:
        """Signal that ``span`` has closed. Base implementation: no-op."""
        return None
