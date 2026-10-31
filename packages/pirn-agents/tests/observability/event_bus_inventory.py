"""``EventBusInventory`` — every ``pirn_agents`` class that runs an event channel of its own.

``pirn_agents.observability`` once forked its own event stream — a ``Tracer``
opening ``Span``\\ s against a pluggable ``ObservabilitySink`` — entirely
separate from core's ``StatusManager``/``Emitter`` stream that every other
domain's telemetry flows through, and carrying no ``run_id``/``knot_id`` core
could correlate against its own lineage. WS4a replaced it with
:class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`, which
emits a core ``StatusEvent`` through the run's own emitters.

Detection is the *shape*, not a name list. The version this replaced held a
frozen set of nine deleted class names and asked which modules imported them —
a gate that catches the resurrection of those exact nine names and nothing else,
so a second event bus written from scratch under any other name passed it
silently. What makes something a second event bus is structural: it takes a
callable from a caller, keeps it, and later calls what it kept. That is what
:meth:`~tests.source_shapes.SourceShapes.own_event_channels` looks for, on every
class in ``pirn_agents``, whatever the register and publish methods are called.

A class that hands an event to the run's emitters (``EmitterFanout.emit_status``)
keeps no subscriber list of its own and is not a channel.
"""

from __future__ import annotations

from tests.agents_source_index import AgentsSourceIndex
from tests.source_shapes import SourceShapes


class EventBusInventory:
    """Discovers ``pirn_agents`` classes that register and deliver to their own subscribers."""

    @staticmethod
    def discover() -> dict[str, frozenset[str]]:
        """Return ``{"relative/path.py::ClassName": {channel attribute, ...}}``.

        One walk of the package (see
        :class:`~tests.agents_source_index.AgentsSourceIndex`); every class is
        scanned, no module list and no name list scopes it.
        """
        found: dict[str, frozenset[str]] = {}
        for label, (_subject, node) in AgentsSourceIndex.classes().items():
            channels = SourceShapes.own_event_channels(node)
            if channels:
                found[label] = channels
        return found
