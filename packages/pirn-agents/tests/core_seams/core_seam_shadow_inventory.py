"""``CoreSeamShadowInventory`` — every ``pirn_agents`` class that re-implements a core seam.

The "agents speaks core" ADR (WS0) adds six seams to ``pirn-core`` so agents
can stop carrying parallel implementations of core verbs: ``KnotConfig.retry``/
``KnotConfig.timeout``, the run-scoped nesting guard (``RunNesting``,
``RunContextVars``), the declared input schema (``Knot.input_json_schema``), the
admission gate and its runtime feedback (``Admission``, ``ConcurrencyLimits``,
``AdmissionObserver``), the ``Check`` node role, and the awaitable
``LoopSubTapestry`` loop step.

A shadow is recognised by its **shape**, never by its name. The version this
replaced matched class names against a per-seam list of regexes
(``^RetryPolicy$``, ``^BackpressureSemaphore$``, ``^ParallelToolExecutor$``, …)
and excluded anything whose base name was the core class. Both halves fail the
same way: renaming the class, or re-parenting it onto a different base, empties
the seam's inventory while the parallel implementation lives on — and a class
that never had one of those names was never looked at. Every seam below is a
:class:`~tests.source_shapes.SourceShapes` predicate over what the class
actually does, so neither a rename nor a re-parent hides it.

Scope is every class in ``pirn_agents``, taken from
:class:`~tests.agents_source_index.AgentsSourceIndex`: one walk, runtime
membership, no directory list and no class-name list.
"""

from __future__ import annotations

import ast

from pirn.core.knot import Knot
from pirn.nodes.check import Check

from tests.agents_source_index import AgentsSourceIndex
from tests.source_shapes import SourceShapes


class CoreSeamShadowInventory:
    """Discovers ``pirn_agents`` classes that carry a WS0 core seam's shape."""

    @staticmethod
    def shadows_retry_or_timeout(_subject: type, node: ast.ClassDef) -> bool:
        """Whether the class bounds time or retries by hand.

        ``KnotConfig(timeout=)`` raises ``KnotTimeoutError`` and
        ``KnotConfig(retry=)`` runs a ``KnotRetryPolicy`` under core's
        ``GovernedDispatch``. A hand-rolled ``wait_for``/``timeout``, or a loop
        that swallows an exception and goes round again, is the same policy
        written where the run cannot see it.
        """
        return SourceShapes.bounds_time_by_hand(node) or SourceShapes.has_retry_loop(node)

    @staticmethod
    def shadows_nesting_guard(_subject: type, node: ast.ClassDef) -> bool:
        """Whether the class keeps run-scoped ambient state of its own.

        Core's ``RunContextVars``/``RunNesting`` is the run's ambient state,
        and the depth and cycle guards read it. A ``ContextVar`` of the class's
        own is a second, uncorrelated one.
        """
        return SourceShapes.constructs_context_var(node)

    @staticmethod
    def shadows_input_schema(_subject: type, node: ast.ClassDef) -> bool:
        """Whether the class derives an argument schema from a callable.

        ``Knot.input_json_schema`` derives the declared inputs from
        ``process()``. Reaching for ``inspect.signature`` / ``get_type_hints``
        / ``get_annotations`` builds a second schema that can disagree with it.
        """
        return SourceShapes.introspects_signature(node)

    @staticmethod
    def shadows_admission_feedback(_subject: type, node: ast.ClassDef) -> bool:
        """Whether the class caps or paces work itself.

        A ``Semaphore``/``CapacityLimiter`` of its own, or a clock-and-sleep
        pacer, is a budget core's ``Admission``/``ConcurrencyLimits`` cannot
        see, chain, or steer from an ``AdmissionObserver``.
        """
        return SourceShapes.constructs_concurrency_primitive(node) or SourceShapes.paces_by_clock(
            node
        )

    @staticmethod
    def shadows_check_role(subject: type, node: ast.ClassDef) -> bool:
        """Whether a knot returns a bare pass/fail verdict without being a ``Check``.

        A knot whose output is a ``bool`` is a predicate on the run, which is
        what core's ``Check`` role is: a ``Gate(check=)`` reads it, a failing
        verdict makes downstream ``Skipped`` rather than a falsy value someone
        has to remember to test. A ``bool``-returning knot that is not a
        ``Check`` carries the role without the wiring.
        """
        if not issubclass(subject, Knot) or issubclass(subject, Check):
            return False
        process = SourceShapes.methods_of(node).get("process")
        return process is not None and SourceShapes.returns_bare_verdict(process)

    @staticmethod
    def shadows_async_loop_step(_subject: type, node: ast.ClassDef) -> bool:
        """Whether the class drives an inner engine run from a loop of its own.

        Core's awaitable ``LoopSubTapestry`` step owns iteration. A method that
        loops over run-time data *and* awaits ``self._run_inner`` has written
        the step by hand: either the run sits inside the loop (one engine round
        trip per item, so the items' lineage is N unrelated runs) or the loop
        builds the run's nodes (N siblings declared one at a time, with their
        ids, dedup and ordering hand-managed).
        """
        return SourceShapes.steps_inner_run_by_hand(node)

    @classmethod
    def seams(cls) -> dict[str, str]:
        """Return ``{seam: the core seam it shadows}`` — the rules this gate enforces."""
        return {
            "retry_timeout": "KnotConfig.retry / KnotConfig.timeout",
            "nesting": "RunContextVars / RunNesting",
            "input_schema": "Knot.input_json_schema",
            "admission_feedback": "Admission / ConcurrencyLimits / AdmissionObserver",
            "check_role": "Check + Gate(check=)",
            "async_loop_step": "LoopSubTapestry's awaitable step",
        }

    @classmethod
    def is_shadow(cls, seam: str, subject: type, node: ast.ClassDef) -> bool:
        """Whether ``subject`` carries ``seam``'s shape."""
        detectors = {
            "retry_timeout": cls.shadows_retry_or_timeout,
            "nesting": cls.shadows_nesting_guard,
            "input_schema": cls.shadows_input_schema,
            "admission_feedback": cls.shadows_admission_feedback,
            "check_role": cls.shadows_check_role,
            "async_loop_step": cls.shadows_async_loop_step,
        }
        return detectors[seam](subject, node)

    @classmethod
    def discover(cls) -> dict[str, frozenset[str]]:
        """Return ``{seam: {"relative/path.py::ClassName", ...}}`` over ``pirn_agents``."""
        found: dict[str, set[str]] = {seam: set() for seam in cls.seams()}
        for label, (subject, node) in AgentsSourceIndex.classes().items():
            for seam in cls.seams():
                if cls.is_shadow(seam, subject, node):
                    found[seam].add(label)
        return {seam: frozenset(labels) for seam, labels in found.items()}
