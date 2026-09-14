"""Guard: the deleted "second event bus" stays deleted (ADR agents-speaks-core WS4a).

``pirn_agents.observability`` once forked its own event stream — a ``Tracer``
opening ``Span``\\ s against a pluggable ``ObservabilitySink`` — entirely
separate from core's ``StatusManager``/``Emitter`` stream that every other
domain's telemetry already flows through. WS4a replaced it with
:class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`,
which emits a core ``StatusEvent`` (carrying ``run_id``/``knot_id`` sourced
from core, not stamped on by hand) through the run's own emitters.

``Tracer``/``Span``/``SpanKind``/``SpanStatus``/``OpenSpanEntry``/
``ObservabilitySink``/``OtelSink``/``LoggingSink``/
``SpanEmittingToolInvocationHook`` are deleted (PIR-864). This guard asserts
that no module in ``pirn_agents`` imports any of those names from
``pirn_agents.observability.*``, so reintroducing the plane — or a module of
the same name — fails here.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.observability.event_bus_inventory import EventBusInventory


class TestDeletedEventBusStaysDeleted(unittest.TestCase):
    """No module imports a deleted event-bus name."""

    def test_no_module_imports_a_deleted_name(self) -> None:
        found = EventBusInventory.discover_modules()
        assert found == {}, found


class TestDetectorIsDiscriminating(unittest.TestCase):
    """The detector must fire on the shape it names, and not on clean code."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _scan(self, source: str) -> frozenset[str]:
        path = Path(self._tmp.name) / "module_under_test.py"
        path.write_text(source)
        return EventBusInventory._imported_deleted_names(path)

    def test_clean_module_trips_nothing(self) -> None:
        hit = self._scan(
            "from pirn.core.knot import Knot\n"
            "from pirn_agents.observability.agent_call_recorder import AgentCallRecorder\n"
        )
        assert hit == frozenset()

    def test_direct_submodule_import_trips(self) -> None:
        hit = self._scan("from pirn_agents.observability.tracer import Tracer\n")
        assert hit == frozenset({"Tracer"})

    def test_package_level_import_trips(self) -> None:
        hit = self._scan("from pirn_agents.observability import ObservabilitySink\n")
        assert hit == frozenset({"ObservabilitySink"})

    def test_aliased_import_still_trips_on_the_original_name(self) -> None:
        hit = self._scan("from pirn_agents.observability.tracer import Tracer as T\n")
        assert hit == frozenset({"Tracer"})

    def test_multiple_deleted_names_are_all_captured(self) -> None:
        hit = self._scan("from pirn_agents.observability.span import Span, SpanKind, SpanStatus\n")
        assert hit == frozenset({"Span", "SpanKind", "SpanStatus"})

    def test_unrelated_module_import_does_not_trip(self) -> None:
        hit = self._scan("from pirn_agents.tools.tool import Tool\n")
        assert hit == frozenset()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
