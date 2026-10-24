"""``ExecutionPlaneReachThroughInventory`` — every site that configures another
object by writing its private state.

The "agents speaks core" ADR (WS0b) makes an inner run inherit the enclosing
run's *execution plane* — dispatcher, admission gate and its
``ConcurrencyLimits``, ``AdmissionObserver``s, replay posture, identity
resolver — the way ``SubTapestry._run_inner`` already forwards the history, the
data store, the transport and the emitters. Before that seam existed, the only
way to point an inner run at a particular dispatcher or group cap was to reach
into the inner tapestry and assign ``tapestry._dispatcher`` /
``tapestry._concurrency`` / ``tapestry._admission_observers`` directly. With the
seam in place the same effect is ``_run_inner(dispatcher=, concurrency=,
admission_observers=)`` or the overridable ``_inner_*`` hooks, and a run started
with none of them simply inherits the enclosing plane.

The detector is the *shape*, not a field list. The version this replaced held a
frozen set of eleven ``Tapestry`` field names, which answers only for the fields
someone thought to write down: a twelfth private field, or the same reach-through
against any other object, went unseen. What is actually wrong is assigning a
``_private`` attribute on an object that is not your own — configuring something
by reaching past its surface — so that is what is detected, on any attribute and
any receiver. ``self``, ``cls``, ``super()``, the enclosing class, and a local
derived from ``self`` in the same scope (``clone = copy.copy(self)``) are the
object's own state and are never reach-throughs.
"""

from __future__ import annotations

import ast

from tests.agents_source_index import AgentsSourceIndex
from tests.source_shapes import SourceShapes


class ExecutionPlaneReachThroughInventory:
    """Discovers ``pirn_agents`` sites that assign another object's private state."""

    @staticmethod
    def reach_throughs_in(tree: ast.AST) -> dict[str, frozenset[str]]:
        """Return ``{enclosing scope: {assigned target, ...}}`` for one parsed module.

        The scope is the top-level class's name, or ``<module>`` for anything
        written outside one.
        """
        own_names = frozenset(
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        )
        found: dict[str, frozenset[str]] = {}
        for scope_name, scope in ExecutionPlaneReachThroughInventory._scopes(tree):
            writes = SourceShapes.foreign_private_writes(scope, own_names)
            if writes:
                found[scope_name] = writes
        return found

    @staticmethod
    def _scopes(tree: ast.AST) -> list[tuple[str, ast.AST]]:
        """Top-level classes by name, plus everything else under ``<module>``."""
        if not isinstance(tree, ast.Module):
            return [("<module>", tree)]
        scopes: list[tuple[str, ast.AST]] = []
        rest = ast.Module(body=[], type_ignores=[])
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                scopes.append((node.name, node))
            else:
                rest.body.append(node)
        scopes.append(("<module>", rest))
        return scopes

    @staticmethod
    def discover() -> dict[str, frozenset[str]]:
        """Return ``{"relative/path.py::Scope": {assigned target, ...}}`` over ``pirn_agents``."""
        found: dict[str, frozenset[str]] = {}
        for relative, tree in AgentsSourceIndex.modules().items():
            for scope_name, writes in (
                ExecutionPlaneReachThroughInventory.reach_throughs_in(tree)
            ).items():
                found[f"{relative}::{scope_name}"] = writes
        return found
