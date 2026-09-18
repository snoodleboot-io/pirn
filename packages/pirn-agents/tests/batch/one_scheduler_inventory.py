"""``OneSchedulerInventory`` — every ``pirn_agents`` class that schedules work itself.

ADR agents-speaks-core, WS4b ("one scheduler"): work is dispatched by the core
engine — ``Map``/``Aggregator`` declare the fan-out, ``Admission`` +
``ConcurrencyLimits`` admit it, ``GovernedDispatch`` runs each attempt, and
``RunHistory`` is what a resumed batch reads. A second scheduler inside a class —
a ``gather``/``TaskGroup``/``create_task`` of its own, a private
``Semaphore``, a clock-and-sleep pacer — schedules work the engine cannot see,
cap, chain under an enclosing cap, cancel, record or replay.

Two things changed from the version this replaced. Its detectors keyed on names:
``asyncio.wait``/``gather``/``ensure_future`` by attribute, a callable whose name
*ends in* ``Semaphore``, and a reference to one of four pinned session-store class
names (``SessionStore``, ``RunCheckpoint``, ``RunState``, ``BatchCheckpointer``) —
so a ``TaskGroup``, a ``CapacityLimiter``, a hand-rolled pacer, or any renamed
checkpoint type went unseen. And its scope was a pinned list of three directories
(``batch``, ``performance``, ``resilience``), so the same private scheduler
written anywhere else in the package was out of scope by construction. Here the
detectors are :class:`~tests.source_shapes.SourceShapes` shapes and the scope is
every class in ``pirn_agents``.
"""

from __future__ import annotations

import ast

from tests.agents_source_index import AgentsSourceIndex
from tests.source_shapes import SourceShapes


class OneSchedulerInventory:
    """Discovers the classes that dispatch, cap or pace work outside the engine."""

    @staticmethod
    def schedules_its_own_tasks(node: ast.ClassDef) -> bool:
        """Whether the class calls a task/concurrency scheduler primitive.

        ``gather``, ``create_task``, ``ensure_future``, ``as_completed``,
        ``TaskGroup``, ``create_task_group``, ``run_in_executor``, a thread or
        process pool, or ``asyncio.wait``: N units of work the engine did not
        schedule, so nothing records, admits, orders or cancels them.
        """
        return SourceShapes.fans_out_by_hand(node)

    @staticmethod
    def holds_its_own_concurrency_budget(node: ast.ClassDef) -> bool:
        """Whether the class constructs a private in-flight budget.

        A cap the engine's ``Admission``/``ConcurrencyLimits`` cannot see,
        chain beneath an enclosing cap, or steer from an ``AdmissionObserver``.
        """
        return SourceShapes.constructs_concurrency_primitive(node)

    @staticmethod
    def paces_its_own_admission(node: ast.ClassDef) -> bool:
        """Whether the class reads a clock and sleeps in one scope.

        A token bucket or rate limiter of its own: admission decided where the
        run cannot observe or override it.
        """
        return SourceShapes.paces_by_clock(node)

    @classmethod
    def discover(cls) -> dict[str, frozenset[str]]:
        """Return ``{shape: {"relative/path.py::ClassName", ...}}`` over ``pirn_agents``."""
        checks = {
            "own_task_scheduling": cls.schedules_its_own_tasks,
            "own_concurrency_budget": cls.holds_its_own_concurrency_budget,
            "own_admission_pacing": cls.paces_its_own_admission,
        }
        found: dict[str, set[str]] = {shape: set() for shape in checks}
        for label, (_subject, node) in AgentsSourceIndex.classes().items():
            for shape, check in checks.items():
                if check(node):
                    found[shape].add(label)
        return {shape: frozenset(labels) for shape, labels in found.items()}
