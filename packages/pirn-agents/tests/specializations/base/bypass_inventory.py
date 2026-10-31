"""``BypassInventory`` — every ``Knot`` in ``pirn_agents`` that does its own work.

A ``Knot`` promises the engine's guarantees: an ``Ok | Err | Skipped`` per
knot, a lineage row, determinism, replay, scheduling, cancellation. It
delivers them only for work the engine *runs*. Work the knot performs itself —
awaiting a collaborator in a loop, fanning calls out by hand, timing or
retrying them itself, counting its own in-flight budget, pacing itself off a
clock — satisfies the type signature and delivers none of it.

Every detector here is a :class:`~tests.source_shapes.SourceShapes` *shape*
read off the AST, never a method or class name. The version this replaced read
only the bodies of methods literally called ``process()``, and recognised a
provider call only when it was named ``chat``/``complete``/``invoke``/
``search``; renaming a provider method, or moving the call into a helper,
emptied the ratchet while the bypass lived on. A shape cannot be renamed away:
``await store.store(key, payload)`` in a loop is the same shape as
``await llm.chat(prompt)`` in a loop, and both are found here.

Scope is every ``Knot`` subclass in ``pirn_agents``, decided at runtime by
``issubclass`` (see :class:`~tests.agents_source_index.AgentsSourceIndex`), and
the body scanned is the class's *whole* body plus any ``pirn_agents`` base it
inherits from — a bypass is a property of what a knot does, not of which method
it does it in.
"""

from __future__ import annotations

import ast

from tests.agents_source_index import AgentsSourceIndex
from tests.source_shapes import SourceShapes


class BypassInventory:
    """Classifies every ``Knot``'s body by the engine-bypass shapes it carries."""

    @staticmethod
    def scanned_bodies(subject: type) -> list[ast.ClassDef]:
        """Return ``subject``'s own class body and every ``pirn_agents`` base's.

        A method a mixin defines and ``subject`` never overrides still runs
        as ``subject``, so it is scanned as ``subject``.
        """
        return [node for _label, _base, node in AgentsSourceIndex.agents_mro_nodes(subject)]

    @staticmethod
    def awaits_collaborator_out_of_band(node: ast.ClassDef) -> bool:
        """Whether the class awaits another object's work in a loop or a fan-out.

        The engine's own way to run N collaborator calls is N sibling knots —
        an ``Aggregator`` fan-out, or a ``LoopSubTapestry`` when the calls
        depend on each other. A Python loop that awaits them, or a
        ``gather``/``TaskGroup`` handed them, produces values with no lineage
        row, no per-call ``Result``, and nothing the engine can schedule,
        cache, replay or cancel.
        """
        effectful = SourceShapes.effectful_methods(SourceShapes.methods_of(node))
        return SourceShapes.loop_awaits_collaborator(
            node, effectful
        ) or SourceShapes.fan_out_awaits_collaborator(node, effectful)

    @staticmethod
    def bounds_or_retries_by_hand(node: ast.ClassDef) -> bool:
        """Whether the class times or retries work itself.

        ``KnotConfig(timeout=)`` and ``KnotConfig(retry=)`` are the engine's,
        and core's ``GovernedDispatch`` owns the backoff between attempts. A
        hand-rolled ``wait_for``/``timeout`` or a loop that swallows an
        exception and goes round again records neither the attempt count nor
        the timeout as anything the run can see.
        """
        return SourceShapes.bounds_time_by_hand(node) or SourceShapes.has_retry_loop(node)

    @staticmethod
    def holds_own_concurrency_budget(node: ast.ClassDef) -> bool:
        """Whether the class constructs a private in-flight budget.

        A ``Semaphore`` or ``CapacityLimiter`` of its own is a cap the
        engine's ``Admission``/``ConcurrencyLimits`` cannot see, chain under
        an enclosing cap, or steer from an ``AdmissionObserver``.
        """
        return SourceShapes.constructs_concurrency_primitive(node)

    @staticmethod
    def paces_itself_by_clock(node: ast.ClassDef) -> bool:
        """Whether the class reads a clock and sleeps in one scope.

        A token bucket or rate limiter written by hand: admission the engine
        neither performs nor records.
        """
        return SourceShapes.paces_by_clock(node)

    # -- control-flow vocabulary (a separate gate) ---------------------------
    #
    # ``test_control_flow_vocabulary.py`` is a different ratchet on a different
    # question — does a ``process()`` *speak* the engine's vocabulary (declare
    # a graph) rather than *run* the work — and it reads these four. They stay
    # here because that gate owns them; they are not part of the bypass rules
    # above and no allowlist hangs off them.

    @staticmethod
    def discover_process_methods() -> dict[str, ast.AST]:
        """Return ``{"relative/path.py::ClassName": process_ast}`` for every knot's own ``process()``."""
        return {
            label: method
            for label, (_knot, node) in AgentsSourceIndex.knots().items()
            if (method := SourceShapes.methods_of(node).get("process")) is not None
        }

    @staticmethod
    def discover_agent_pipeline_process_methods() -> dict[str, ast.AST]:
        """Like :meth:`discover_process_methods`, narrowed to ``AgentPipeline`` subclasses."""
        from pirn_agents.specializations.base.agent_pipeline import AgentPipeline

        return {
            label: method
            for label, (knot, node) in AgentsSourceIndex.knots().items()
            if issubclass(knot, AgentPipeline)
            and (method := SourceShapes.methods_of(node).get("process")) is not None
        }

    @staticmethod
    def defines_inline_source(process: ast.AST) -> bool:
        """Whether a ``Source`` subclass is declared inside the body.

        A class built inside ``process()`` to re-inject an already-resolved
        value is what :class:`~pirn.core.parameter.Parameter` is for.
        """
        return any(
            isinstance(node, ast.ClassDef)
            and any(isinstance(base, ast.Name) and base.id == "Source" for base in node.bases)
            for node in ast.walk(process)
        )

    @staticmethod
    def is_identity_knot(process: ast.AST) -> bool:
        """Whether the body does nothing but return one of its own parameters.

        A knot that computes nothing exists only to make an already-known
        value visible as a graph node; ``Parameter`` is the sanctioned way.
        """
        if not isinstance(process, ast.AsyncFunctionDef | ast.FunctionDef):
            return False
        args = process.args
        parameters = {
            arg.arg
            for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)
            if arg.arg not in {"self", "cls"}
        }
        body = [stmt for stmt in process.body if not BypassInventory._is_docstring(stmt)]
        if len(body) != 1:
            return False
        (statement,) = body
        return (
            isinstance(statement, ast.Return)
            and isinstance(statement.value, ast.Name)
            and statement.value.id in parameters
        )

    @staticmethod
    def _is_docstring(statement: ast.stmt) -> bool:
        return (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        )

    @staticmethod
    def process_returns_any(process: ast.AST) -> bool:
        """Whether ``process()``'s return annotation is a bare ``Any``."""
        if not isinstance(process, ast.AsyncFunctionDef | ast.FunctionDef):
            return False
        returns = process.returns
        return isinstance(returns, ast.Name) and returns.id == "Any"

    @classmethod
    def discover(cls) -> dict[str, frozenset[str]]:
        """Return ``{shape: {"relative/path.py::ClassName", ...}}`` over every knot."""
        checks = {
            "collaborator_await_out_of_band": cls.awaits_collaborator_out_of_band,
            "hand_rolled_time_bound_or_retry": cls.bounds_or_retries_by_hand,
            "own_concurrency_budget": cls.holds_own_concurrency_budget,
            "clock_pacing": cls.paces_itself_by_clock,
        }
        found: dict[str, set[str]] = {shape: set() for shape in checks}
        for label, (knot, _node) in AgentsSourceIndex.knots().items():
            bodies = cls.scanned_bodies(knot)
            for shape, check in checks.items():
                if any(check(body) for body in bodies):
                    found[shape].add(label)
        return {shape: frozenset(labels) for shape, labels in found.items()}
