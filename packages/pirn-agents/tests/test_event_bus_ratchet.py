"""Guard: there is one event stream, and it is core's (ADR agents-speaks-core WS4a).

``pirn_agents.observability`` once forked its own — a ``Tracer`` opening
``Span``\\ s against a pluggable ``ObservabilitySink``, separate from core's
``StatusManager``/``Emitter`` stream and carrying no ``run_id``/``knot_id`` core
could correlate against its lineage. WS4a replaced it with
:class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`, which
emits a core ``StatusEvent`` through the run's own emitters.

There is no name list here. The version this replaced asked which modules
imported one of nine deleted class names, which catches the resurrection of
those nine names and nothing else — a second bus written from scratch under any
other name passed it silently. The assertion below is the rule itself: **no
class keeps its own subscribers and delivers to them**.
:class:`TestEventChannelDetectorFires` proves the detector fires, so an empty
finding means an empty tree and not a blind detector.
"""

from __future__ import annotations

import ast
import unittest

from tests.agents_source_index import AgentsSourceIndex
from tests.observability.event_bus_inventory import EventBusInventory
from tests.source_shapes import SourceShapes


class TestThereIsOneEventStream(unittest.TestCase):
    """No class runs an event channel of its own. Asserted, not inventoried."""

    def test_the_walk_is_not_vacuous(self) -> None:
        """A guard that scans nothing passes for the wrong reason."""
        assert len(AgentsSourceIndex.classes()) >= 500, len(AgentsSourceIndex.classes())

    def test_no_class_keeps_its_own_subscribers(self) -> None:
        found = EventBusInventory.discover()
        assert found == {}, {label: sorted(channels) for label, channels in found.items()}


class TestEventChannelDetectorFires(unittest.TestCase):
    """The detector fires on the shape it names, and not on core's emitter path."""

    @staticmethod
    def _channels(source: str) -> frozenset[str]:
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef))
        return SourceShapes.own_event_channels(node)

    def test_rule_fires_on_a_subscriber_list_delivered_to_in_a_loop(self) -> None:
        assert self._channels(
            "class Tracer:\n"
            "    def __init__(self):\n"
            "        self._sinks = []\n"
            "    def subscribe(self, sink):\n"
            "        self._sinks.append(sink)\n"
            "    async def publish(self, event):\n"
            "        for sink in self._sinks:\n"
            "            await sink(event)\n"
        ) == frozenset({"_sinks"})

    def test_rule_fires_on_a_handler_map_called_by_key(self) -> None:
        """A different spelling of the same channel; no name in common with the last one."""
        assert self._channels(
            "class Dispatcher:\n"
            "    def on(self, topic, handler):\n"
            "        self._handlers[topic] = handler\n"
            "    async def fire(self, topic, payload):\n"
            "        return await self._handlers[topic](payload)\n"
        ) == frozenset({"_handlers"})

    def test_rule_fires_on_a_set_of_listeners_delivered_to_by_comprehension(self) -> None:
        assert self._channels(
            "class Bus:\n"
            "    def register(self, listener):\n"
            "        self._listeners.add(listener)\n"
            "    def emit(self, event):\n"
            "        return [listener(event) for listener in self._listeners]\n"
        ) == frozenset({"_listeners"})

    def test_rule_ignores_a_registry_that_never_delivers(self) -> None:
        """Holding things is not a channel; calling what you hold is."""
        assert (
            self._channels(
                "class Toolset:\n"
                "    def register(self, name, tool):\n"
                "        self._tools[name] = tool\n"
                "    def get(self, name):\n"
                "        return self._tools.get(name)\n"
            )
            == frozenset()
        )

    def test_rule_ignores_calling_collaborators_it_was_not_given(self) -> None:
        """Iterating something the class did not collect from callers is not a channel."""
        assert (
            self._channels(
                "class Runner:\n"
                "    async def run(self, steps):\n"
                "        for step in steps:\n"
                "            step()\n"
            )
            == frozenset()
        )

    def test_rule_ignores_emitting_through_the_runs_emitters(self) -> None:
        assert (
            self._channels(
                "class AgentCallRecorder:\n"
                "    async def record(self, event):\n"
                "        await EmitterFanout.emit_status(event)\n"
            )
            == frozenset()
        )
