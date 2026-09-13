"""``ExecutionPlaneReachThroughInventory`` — find every ``pirn_agents`` site that
configures an inner run by writing a ``Tapestry``'s private fields.

The "agents speaks core" ADR (2026-09-13), WS0b, makes an inner run inherit
the enclosing run's *execution plane* — its dispatcher, its admission gate
(and therefore its ``ConcurrencyLimits``), its ``AdmissionObserver``s, its
replay posture and its identity resolver — the way ``SubTapestry._run_inner``
already forwards the history, the data store, the transport and the emitters.
Before that seam existed, the only way a ``SubTapestry`` subclass could point
its inner run at a particular dispatcher or group cap was to reach into the
inner tapestry and assign ``tapestry._dispatcher`` / ``tapestry._concurrency``
/ ``tapestry._admission_observers`` directly (WS4b's ``MapAgent``
``_apply_run_settings`` was the one site that did).  Those writes are what
this inventory burns down: with the seam in place the same effect is
``SubTapestry._run_inner(dispatcher=, concurrency=, admission_observers=)`` or
the overridable ``_inner_dispatcher`` / ``_inner_concurrency`` /
``_inner_admission_observers`` hooks, and a run started with none of them
simply inherits the enclosing run's plane.

Shared by ``test_execution_plane_reach_through.py`` (the frozen ratchet
asserted by exact equality) and by nothing else.

Detection is a source-only AST pass: an ``ast.Attribute`` whose ``attr`` is one
of the private ``Tapestry`` execution fields and whose value is *not* ``self``
or ``cls`` — a class's own ``self._history`` is its own business; a write or
read of ``tapestry._history`` is the reach-through.  Both reads and writes
count: reading a private field to *decide* how to configure the inner run is
the same coupling as writing one.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import ClassVar

import pirn_agents


class ExecutionPlaneReachThroughInventory:
    """Discovers ``pirn_agents`` sites that touch a tapestry's private execution fields."""

    #: The private ``Tapestry`` fields that make up a run's execution plane and
    #: its observability wiring.  ``SubTapestry._run_inner`` and
    #: ``_IterationChainKnot`` forward every one of them; downstream code has
    #: no business assigning them.
    PRIVATE_TAPESTRY_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "_dispatcher",
            "_concurrency",
            "_admission_observers",
            "_max_nesting_depth",
            "_identity_resolver",
            "_history",
            "_data_store",
            "_transport",
            "_emitters",
            "_emitter_error_policy",
            "_traceback_filter",
        }
    )

    @staticmethod
    def _is_own_reference(value: ast.expr) -> bool:
        """Whether *value* is ``self`` or ``cls`` — a class touching its own state."""
        return isinstance(value, ast.Name) and value.id in {"self", "cls"}

    @classmethod
    def is_reach_through(cls, node: ast.AST) -> bool:
        """Whether *node* reads or writes a private execution field of another object."""
        if not isinstance(node, ast.Attribute):
            return False
        if node.attr not in cls.PRIVATE_TAPESTRY_FIELDS:
            return False
        return not cls._is_own_reference(node.value)

    @classmethod
    def reach_throughs_in(cls, tree: ast.AST) -> set[str]:
        """Return the enclosing-scope names (``ClassName`` or ``<module>``) with a reach-through."""
        found: set[str] = set()
        for scope_name, scope in cls._scopes(tree):
            if any(cls.is_reach_through(node) for node in ast.walk(scope)):
                found.add(scope_name)
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

    @classmethod
    def discover(cls) -> frozenset[str]:
        """Return ``{"relative/path.py::Scope", ...}`` over ``pirn_agents``."""
        root = Path(pirn_agents.__path__[0])
        found: set[str] = set()
        for path in sorted(root.rglob("*.py")):
            if any(part in {"tests", "__pycache__"} for part in path.parts):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            relative = path.relative_to(root).as_posix()
            for scope_name in cls.reach_throughs_in(tree):
                found.add(f"{relative}::{scope_name}")
        return frozenset(found)
