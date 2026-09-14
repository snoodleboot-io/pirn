"""Ratchet: freeze the ``pirn_agents`` classes that schedule outside the core engine.

The "agents speaks core" ADR (2026-09-13), WS4b ("one scheduler"): batch
execution should be the core engine's ``Map``/``Aggregator``/``Dispatcher``/
``Admission`` — not a private ``asyncio.wait`` loop, a hand-held
``asyncio.Semaphore``, or a checkpoint store outside ``RunHistory``. WS4b's
own migration (``MapAgent`` → per-item knots + ``Aggregator``;
``AdaptiveConcurrencyController`` → ``AdmissionObserver``) and PIR-864 left
no private scheduler, so ``ASYNCIO_LOOP`` is empty. PIR-866 migrated
the two primitives WS4b did not own the blast radius for
(``BackpressureSemaphore``, ``Bulkhead``) onto a real
``LimitedAdmission`` per pool, and PIR-864 deletes both of those too
(``OWN_CONCURRENCY_LIMIT`` was already empty).

The allowlists are asserted by **exact equality**, deliberately:

* adding a new shadow fails, because the finding is not in the list;
* migrating one *without* updating the list also fails, because the list
  still names it.

The second half is what keeps the list from rotting into a lie. Empty lists
are kept as ``frozenset()`` assertions, not deleted, so a reintroduced
private loop/semaphore/checkpoint still fails loudly here.
"""

from __future__ import annotations

import ast
import unittest

from tests.batch.one_scheduler_inventory import OneSchedulerInventory

# --- known shadows, frozen (ADR agents-speaks-core, WS4b) -------------------

# BatchScheduler deleted (PIR-864); see the module docstring.
ASYNCIO_LOOP: frozenset[str] = frozenset()

# PIR-866 migrated both off their own asyncio.Semaphore, and PIR-864 deleted
# BackpressureSemaphore/Bulkhead outright -- see the module docstring. Empty,
# not deleted: a re-introduced private semaphore anywhere in these three
# directories still fails loudly here.
OWN_CONCURRENCY_LIMIT: frozenset[str] = frozenset()

# BatchCheckpointer/BatchScheduler deleted (PIR-864). BatchProgress's
# to_run_state()/from_run_state() RunState bridge is deleted (PIR-872): it is a
# pure per-fire summary that checkpoints nothing, and resume state is the
# RunHistory lineage query on each item's knot id. Empty, not deleted.
CHECKPOINTS_OUTSIDE_RUN_HISTORY: frozenset[str] = frozenset()


class TestOneSchedulerShadowsAreFrozen(unittest.TestCase):
    """Freeze the shadow inventory. Exact equality in both directions."""

    def setUp(self) -> None:
        self.found = OneSchedulerInventory.discover()

    def test_the_walk_is_not_vacuous(self) -> None:
        """A guard that walks nothing passes for the wrong reason.

        Every inventory is empty now, so vacuity is checked on the walk itself:
        the owned directories must still hold the classes the detectors read.
        """
        assert set(self.found) == {
            "asyncio_loop",
            "own_concurrency_limit",
            "checkpoints_outside_run_history",
        }
        walked = OneSchedulerInventory.walked_class_count()
        assert walked >= 10, walked

    def test_asyncio_loop_shadows_are_frozen(self) -> None:
        found = self.found["asyncio_loop"]
        assert found == ASYNCIO_LOOP, {
            "new shadows": sorted(found - ASYNCIO_LOOP),
            "migrated — remove from ASYNCIO_LOOP": sorted(ASYNCIO_LOOP - found),
        }

    def test_own_concurrency_limit_shadows_are_frozen(self) -> None:
        found = self.found["own_concurrency_limit"]
        assert found == OWN_CONCURRENCY_LIMIT, {
            "new shadows": sorted(found - OWN_CONCURRENCY_LIMIT),
            "migrated — remove from OWN_CONCURRENCY_LIMIT": sorted(OWN_CONCURRENCY_LIMIT - found),
        }

    def test_checkpoints_outside_run_history_are_frozen(self) -> None:
        found = self.found["checkpoints_outside_run_history"]
        assert found == CHECKPOINTS_OUTSIDE_RUN_HISTORY, {
            "new shadows": sorted(found - CHECKPOINTS_OUTSIDE_RUN_HISTORY),
            "migrated — remove from CHECKPOINTS_OUTSIDE_RUN_HISTORY": sorted(
                CHECKPOINTS_OUTSIDE_RUN_HISTORY - found
            ),
        }

    def test_map_agent_no_longer_shadows_anything(self) -> None:
        """The centerpiece of WS4b: MapAgent itself must appear in no list."""
        for detector, labels in self.found.items():
            assert not any(label.endswith("::MapAgent") for label in labels), (detector, labels)

    def test_adaptive_concurrency_controller_no_longer_shadows_anything(self) -> None:
        """It is now an AdmissionObserver; it must own no asyncio loop or semaphore."""
        for detector, labels in self.found.items():
            assert not any(label.endswith("::AdaptiveConcurrencyController") for label in labels), (
                detector,
                labels,
            )


class TestDetectorsAreDiscriminating(unittest.TestCase):
    """The detectors must fire on the shapes they name, and not on clean code.

    Without these, an allowlist that matches a detector which silently
    stopped working would still be green — the failure mode a ratchet is
    most prone to.
    """

    @staticmethod
    def _class_of(source: str) -> ast.ClassDef:
        tree = ast.parse(source)
        return next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))

    def test_asyncio_wait_trips(self) -> None:
        node = self._class_of(
            "class P:\n"
            "    async def run(self, pending):\n"
            "        return await asyncio.wait(pending)\n"
        )
        assert OneSchedulerInventory.schedules_own_asyncio_loop(node)

    def test_bare_gather_trips(self) -> None:
        node = self._class_of(
            "class P:\n    async def run(self, coros):\n        return await gather(*coros)\n"
        )
        assert OneSchedulerInventory.schedules_own_asyncio_loop(node)

    def test_event_wait_method_does_not_trip(self) -> None:
        """A plain ``.wait()`` on an unrelated object (Event, Condition, ...) is not asyncio.wait."""
        node = self._class_of(
            "class P:\n"
            "    def __init__(self):\n"
            "        self._event = Event()\n"
            "    async def wait(self):\n"
            "        await self._event.wait()\n"
        )
        assert not OneSchedulerInventory.schedules_own_asyncio_loop(node)

    def test_engine_dispatch_does_not_trip(self) -> None:
        node = self._class_of(
            "class P(Knot):\n"
            "    async def process(self, items, **_):\n"
            "        return Aggregator(combine=self._merge, _config=KnotConfig(id='a'))\n"
        )
        assert not OneSchedulerInventory.schedules_own_asyncio_loop(node)

    def test_asyncio_semaphore_trips(self) -> None:
        node = self._class_of(
            "class P:\n    def __init__(self):\n        self._sem = asyncio.Semaphore(4)\n"
        )
        assert OneSchedulerInventory.holds_own_concurrency_limit(node)

    def test_composed_named_semaphore_trips(self) -> None:
        node = self._class_of(
            "class P:\n"
            "    def _pool(self, key):\n"
            "        return BackpressureSemaphore(self._config.for_backend(key))\n"
        )
        assert OneSchedulerInventory.holds_own_concurrency_limit(node)

    def test_docstring_mentioning_semaphore_does_not_trip(self) -> None:
        node = self._class_of(
            "class P:\n"
            '    """One shared knob rather than an asyncio.Semaphore(8) per call site."""\n'
            "    max_concurrency: int = 8\n"
        )
        assert not OneSchedulerInventory.holds_own_concurrency_limit(node)

    def test_concurrency_limits_group_does_not_trip(self) -> None:
        node = self._class_of(
            "class P:\n    def limits(self):\n        return ConcurrencyLimits(groups={'g': 4})\n"
        )
        assert not OneSchedulerInventory.holds_own_concurrency_limit(node)

    def test_session_store_type_annotation_trips(self) -> None:
        node = self._class_of(
            "class P:\n    def __init__(self, store: SessionStore) -> None:\n        self._store = store\n"
        )
        assert OneSchedulerInventory.checkpoints_outside_run_history(node)

    def test_run_state_reference_trips(self) -> None:
        node = self._class_of(
            "class P:\n"
            "    def to_state(self):\n"
            "        return RunState(session_id=self.id, cursor=self.cursor)\n"
        )
        assert OneSchedulerInventory.checkpoints_outside_run_history(node)

    def test_docstring_mentioning_session_store_does_not_trip(self) -> None:
        node = self._class_of(
            "class P:\n"
            '    """Bridges to the pre-migration SessionStore for one deprecation cycle."""\n'
            "    pass\n"
        )
        assert not OneSchedulerInventory.checkpoints_outside_run_history(node)

    def test_run_history_reference_does_not_trip(self) -> None:
        node = self._class_of(
            "class P:\n"
            "    def __init__(self, history: RunHistory) -> None:\n"
            "        self._history = history\n"
        )
        assert not OneSchedulerInventory.checkpoints_outside_run_history(node)
