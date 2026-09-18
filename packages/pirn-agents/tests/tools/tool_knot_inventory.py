"""``ToolKnotInventory`` — every knot in ``pirn_agents`` carrying a second execution verb.

ADR "agents speaks core" WS1 makes ``Tool`` a ``Knot`` class: the capability is
the class, one call is an instance with ``KnotConfig(id=call_id)``, the outcome
is the engine's ``Result`` plus its lineage row. A knot has exactly one
execution verb — ``process()`` — because that is the one the engine runs and
records. A second public coroutine that does real work is a way to call the
capability the engine never sees: no ``Ok | Err | Skipped``, no lineage, no
retry, timeout, admission or replay.

Detection is the *shape*, not a name. The version this replaced looked for a
method literally named ``invoke``, for imports of three deleted vocabulary names
(``ToolStatus``, ``ToolSchemaCompiler``, ``ArgumentValidator``), and for
``await <x>.invoke(...)`` call sites — so renaming ``invoke`` to anything else
emptied all three inventories at once while the second verb lived on. What is
actually wrong is *having a second verb*, whatever it is called: a public
``async def`` other than ``process()`` that awaits a collaborator, and that no
base class already declares (an override of a core seam such as
``LoopSubTapestry.astep`` is implementing core's vocabulary, not adding a
second one).

Call sites that await such a verb are the same shape as any other collaborator
await from inside a knot and are found by
``tests/specializations/base/test_no_engine_bypass.py``; there is no separate
call-site inventory here.
"""

from __future__ import annotations

import ast

from tests.agents_source_index import AgentsSourceIndex
from tests.source_shapes import SourceShapes


class ToolKnotInventory:
    """Discovers the public coroutines a knot adds beside ``process()``."""

    @staticmethod
    def second_execution_verbs(node: ast.ClassDef, overrides: frozenset[str]) -> frozenset[str]:
        """Return the public coroutines in ``node`` that do work beside ``process()``.

        ``overrides`` names the methods a base class already declares; those
        implement an inherited seam rather than adding a verb. "Does work" is
        :meth:`~tests.source_shapes.SourceShapes.effectful_methods`: the method
        awaits a collaborator, directly or through a private helper of its own.
        """
        methods = SourceShapes.methods_of(node)
        effectful = SourceShapes.effectful_methods(methods)
        return frozenset(
            name
            for name, method in methods.items()
            if isinstance(method, ast.AsyncFunctionDef)
            and not name.startswith("_")
            and name != "process"
            and name in effectful
            and name not in overrides
        )

    @staticmethod
    def discover() -> dict[str, frozenset[str]]:
        """Return ``{"relative/path.py::ClassName": {verb, ...}}`` over every knot."""
        found: dict[str, frozenset[str]] = {}
        for label, (knot, node) in AgentsSourceIndex.knots().items():
            overrides = AgentsSourceIndex.inherited_method_names(knot, node)
            verbs = ToolKnotInventory.second_execution_verbs(node, overrides)
            if verbs:
                found[label] = verbs
        return found
