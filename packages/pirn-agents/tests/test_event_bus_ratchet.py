"""Guard: freeze the "second event bus" inventory (ADR agents-speaks-core WS4a).

``pirn_agents.observability`` forked its own event stream —
:class:`~pirn_agents.observability.tracer.Tracer` opening
:class:`~pirn_agents.observability.span.Span`\\ s against a pluggable
:class:`~pirn_agents.observability.observability_sink.ObservabilitySink` —
entirely separate from core's ``StatusManager``/``Emitter`` stream that every
other domain's telemetry already flows through. WS4a replaces it with
:class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`,
which emits a core ``StatusEvent`` (carrying ``run_id``/``knot_id`` sourced
from core, not stamped on by hand) through the run's own emitters.

``Tracer``/``Span``/``SpanKind``/``SpanStatus``/``OpenSpanEntry``/
``ObservabilitySink``/``OtelSink``/``LoggingSink``/
``SpanEmittingToolInvocationHook`` stay importable for one deprecation cycle
(the ADR's public-name rule — see PIR-856's common brief) rather than being
deleted outright, so this is a ratchet, not a clean assertion: it freezes
*which modules currently import a deprecated name*, asserted by exact
equality in both directions, exactly like ``tests.specializations.base.
test_no_engine_bypass``:

* a new module picking up one of these names fails, because it is not in
  the allowlist;
* consolidating a module's use of one away *without* updating the allowlist
  also fails, because the allowlist still names it.

Today every hit is inside ``observability/`` itself (the old classes
importing each other) — zero production call sites outside the package ever
adopted this plane (see PIR-856's vocabulary-drift review). The allowlist
below is that starting inventory, frozen before any burn-down in this same
lane.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.observability.event_bus_inventory import EventBusInventory

# --- known deprecated-name importers, frozen ------------------------------
# Every hit today is the old classes importing each other inside
# observability/; nothing outside the package ever adopted this plane.
DEPRECATED_IMPORTERS = {
    "observability/logging_sink.py": frozenset({"ObservabilitySink", "Span"}),
    "observability/observability_sink.py": frozenset({"Span"}),
    "observability/otel_sink.py": frozenset({"ObservabilitySink", "Span", "SpanStatus"}),
    "observability/span.py": frozenset({"ObservabilitySink", "SpanKind", "SpanStatus"}),
    "observability/span_emitting_tool_invocation_hook.py": frozenset(
        {"Span", "SpanKind", "SpanStatus", "Tracer"}
    ),
    "observability/tracer.py": frozenset(
        {"ObservabilitySink", "OpenSpanEntry", "Span", "SpanKind", "SpanStatus"}
    ),
}


class TestEventBusInventoryIsFrozen(unittest.TestCase):
    """Freeze the deprecated event-bus import inventory. Exact equality."""

    def setUp(self) -> None:
        self.found = EventBusInventory.discover_modules()

    def test_the_walk_is_not_vacuous(self) -> None:
        """A guard that finds nothing passes for the wrong reason."""
        assert len(self.found) > 0

    def test_deprecated_importers_are_frozen(self) -> None:
        assert self.found == DEPRECATED_IMPORTERS, {
            "new importers": sorted(set(self.found) - set(DEPRECATED_IMPORTERS)),
            "fixed — remove from DEPRECATED_IMPORTERS": sorted(
                set(DEPRECATED_IMPORTERS) - set(self.found)
            ),
            "changed sets": {
                k: (self.found.get(k), DEPRECATED_IMPORTERS.get(k))
                for k in set(self.found) | set(DEPRECATED_IMPORTERS)
                if self.found.get(k) != DEPRECATED_IMPORTERS.get(k)
            },
        }

    def test_no_module_outside_observability_imports_a_deprecated_name(self) -> None:
        """The one invariant that actually matters: no new adopters.

        Every frozen entry lives inside ``observability/`` itself. If this
        ever finds a hit elsewhere, WS4a's promise — nothing new depends on
        the deprecated plane while the shim cycle runs — is broken.
        """
        outside = {k: v for k, v in self.found.items() if not k.startswith("observability/")}
        assert outside == {}, outside


class TestDetectorIsDiscriminating(unittest.TestCase):
    """The detector must fire on the shape it names, and not on clean code."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _scan(self, source: str) -> frozenset[str]:
        path = Path(self._tmp.name) / "module_under_test.py"
        path.write_text(source)
        return EventBusInventory._imported_deprecated_names(path)

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

    def test_multiple_deprecated_names_are_all_captured(self) -> None:
        hit = self._scan("from pirn_agents.observability.span import Span, SpanKind, SpanStatus\n")
        assert hit == frozenset({"Span", "SpanKind", "SpanStatus"})

    def test_unrelated_module_import_does_not_trip(self) -> None:
        hit = self._scan("from pirn_agents.tools.tool import Tool\n")
        assert hit == frozenset()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
