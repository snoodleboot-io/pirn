"""``EventBusInventory`` — find every module in ``pirn_agents`` that imports a
name from the deleted Tracer/Span observability plane.

Shared by ``test_event_bus_ratchet.py`` the same way ``bypass_inventory.py`` is
shared by ``test_no_engine_bypass.py``: one walk, one answer, which the guard
asserts is empty.

ADR "agents speaks core" (PIR-856, WS4a) replaced this plane —
``Tracer`` opening ``Span``\\ s against a pluggable ``ObservabilitySink``, none
of which carried a ``run_id``/``knot_id`` core could correlate against its own
lineage — with :class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`,
which emits a core ``StatusEvent`` through the run's own emitters. PIR-864
deleted every name of the old plane; this inventory is what proves none of
them comes back.

The scan is a pure AST import-statement walk, not a runtime import — unlike
``BypassInventory`` (which needs ``issubclass`` to find every ``Knot``), the
question here ("does this module import name X from ``pirn_agents.
observability.*``?") is fully answered by the import statement itself, so
nothing needs constructing or executing. It follows ``from ... import NAME``
(with or without ``as``); a bare ``import pirn_agents.observability.tracer``
followed by attribute access would not be caught, but no code in this
codebase uses that style (house convention is ``from module import Name``).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pirn_agents

#: The names of the deleted "second event bus". Importing any of these from
#: ``pirn_agents.observability.*`` is what the guard refuses.
DELETED_NAMES = frozenset(
    {
        "Tracer",
        "Span",
        "SpanKind",
        "SpanStatus",
        "OpenSpanEntry",
        "ObservabilitySink",
        "OtelSink",
        "LoggingSink",
        "SpanEmittingToolInvocationHook",
    }
)


class EventBusInventory:
    """Discovers every module importing a deleted observability name."""

    @staticmethod
    def discover_modules() -> dict[str, frozenset[str]]:
        """Return ``{"relative/path.py": frozenset(names imported)}``.

        Walks every ``.py`` file under ``pirn_agents`` (source, not tests) and
        records which deleted names, if any, each module imports from
        ``pirn_agents.observability.*``. A plain AST walk over every file, not
        a runtime import — the question this answers ("does this module import
        name X from ``pirn_agents.observability.*``?") is fully answered by the
        import statement itself.
        """
        root = Path(pirn_agents.__path__[0])
        found: dict[str, frozenset[str]] = {}
        for path in sorted(root.rglob("*.py")):
            hit = EventBusInventory._imported_deleted_names(path)
            if hit:
                found[str(path.relative_to(root))] = hit
        return found

    @staticmethod
    def _imported_deleted_names(path: Path) -> frozenset[str]:
        """Return the deleted names ``path`` imports from ``observability.*``."""
        tree = ast.parse(path.read_text())
        hit: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if not node.module or not (
                node.module == "pirn_agents.observability"
                or node.module.startswith("pirn_agents.observability.")
            ):
                continue
            for alias in node.names:
                if alias.name in DELETED_NAMES:
                    hit.add(alias.name)
        return frozenset(hit)
