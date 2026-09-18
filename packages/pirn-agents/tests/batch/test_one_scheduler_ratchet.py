"""Guard: there is one scheduler, and it is the core engine's (ADR WS4b).

Work is dispatched by core: ``Map``/``Aggregator`` declare the fan-out,
``Admission`` + ``ConcurrencyLimits`` admit it, ``GovernedDispatch`` runs each
attempt, ``RunHistory`` is what a resumed batch reads. A second scheduler inside
a class schedules work the engine cannot see, cap, chain, cancel, record or
replay.

There is no allowlist and no directory list. The version this replaced froze
three (empty) inventories of class names, scanned only ``batch/``,
``performance/`` and ``resilience/``, and keyed its detectors on
``asyncio.wait``/``gather``/``ensure_future``, a callable ending in
``Semaphore``, and four pinned checkpoint-type names — so a ``TaskGroup``, a
``CapacityLimiter``, a hand-rolled pacer, or the same code in any other
directory was out of scope by construction. Each assertion below is the rule
itself, over the whole package: **no class schedules, caps or paces work
itself**. :class:`TestOneSchedulerDetectorsFire` proves each detector fires, so
an empty finding means an empty tree and not a blind detector.
"""

from __future__ import annotations

import ast
import unittest

from tests.agents_source_index import AgentsSourceIndex
from tests.batch.one_scheduler_inventory import OneSchedulerInventory


class TestThereIsOneScheduler(unittest.TestCase):
    """The engine schedules. Asserted, not inventoried."""

    def setUp(self) -> None:
        self.found = OneSchedulerInventory.discover()

    def test_the_walk_is_not_vacuous(self) -> None:
        """A guard that scans nothing passes for the wrong reason."""
        assert len(AgentsSourceIndex.classes()) >= 500, len(AgentsSourceIndex.classes())

    def test_no_class_schedules_its_own_tasks(self) -> None:
        found = self.found["own_task_scheduling"]
        assert found == frozenset(), sorted(found)

    def test_no_class_holds_its_own_concurrency_budget(self) -> None:
        found = self.found["own_concurrency_budget"]
        assert found == frozenset(), sorted(found)

    def test_no_class_paces_its_own_admission(self) -> None:
        found = self.found["own_admission_pacing"]
        assert found == frozenset(), sorted(found)


class TestOneSchedulerDetectorsFire(unittest.TestCase):
    """Each detector fires on the shape it names, and not on the engine's own levers."""

    @staticmethod
    def _class_of(source: str) -> ast.ClassDef:
        return next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef))

    # -- own task scheduling ----------------------------------------------------

    def test_rule_task_scheduling_fires_on_asyncio_gather(self) -> None:
        assert OneSchedulerInventory.schedules_its_own_tasks(
            self._class_of(
                "class Batch:\n"
                "    async def run(self, coros):\n"
                "        return await asyncio.gather(*coros)\n"
            )
        )

    def test_rule_task_scheduling_fires_on_a_task_group(self) -> None:
        """A shape the name-keyed version had no entry for."""
        assert OneSchedulerInventory.schedules_its_own_tasks(
            self._class_of(
                "class Batch:\n"
                "    async def run(self, items):\n"
                "        async with asyncio.TaskGroup() as group:\n"
                "            for item in items:\n"
                "                group.create_task(self._one(item))\n"
            )
        )

    def test_rule_task_scheduling_fires_on_a_thread_pool(self) -> None:
        assert OneSchedulerInventory.schedules_its_own_tasks(
            self._class_of(
                "class Batch:\n"
                "    def run(self, items):\n"
                "        with ThreadPoolExecutor(max_workers=4) as pool:\n"
                "            return list(pool.map(self._one, items))\n"
            )
        )

    def test_rule_task_scheduling_ignores_an_unrelated_wait(self) -> None:
        """``Event.wait()`` is not ``asyncio.wait``."""
        assert not OneSchedulerInventory.schedules_its_own_tasks(
            self._class_of(
                "class Token:\n"
                "    async def until_cancelled(self):\n"
                "        await self._event.wait()\n"
            )
        )

    def test_rule_task_scheduling_ignores_a_declared_fan_out(self) -> None:
        assert not OneSchedulerInventory.schedules_its_own_tasks(
            self._class_of(
                "class MapAgent:\n"
                "    async def process(self, **per_item):\n"
                "        return Aggregator(combine=self._merge, _config=KnotConfig(id='a'), "
                "**per_item)\n"
            )
        )

    # -- own concurrency budget ----------------------------------------------------

    def test_rule_concurrency_budget_fires_on_an_asyncio_semaphore(self) -> None:
        assert OneSchedulerInventory.holds_its_own_concurrency_budget(
            self._class_of(
                "class Pool:\n    def __init__(self, n):\n        self._slots = asyncio.Semaphore(n)\n"
            )
        )

    def test_rule_concurrency_budget_fires_on_a_capacity_limiter(self) -> None:
        """A shape the ``*Semaphore`` name match could not see."""
        assert OneSchedulerInventory.holds_its_own_concurrency_budget(
            self._class_of(
                "class Pool:\n    def __init__(self, n):\n        self._slots = CapacityLimiter(n)\n"
            )
        )

    def test_rule_concurrency_budget_ignores_a_docstring_mentioning_one(self) -> None:
        assert not OneSchedulerInventory.holds_its_own_concurrency_budget(
            self._class_of(
                "class Pool:\n"
                '    """One group cap rather than an asyncio.Semaphore(8) per call site."""\n'
                "    max_concurrency: int = 8\n"
            )
        )

    def test_rule_concurrency_budget_ignores_the_engines_group_cap(self) -> None:
        assert not OneSchedulerInventory.holds_its_own_concurrency_budget(
            self._class_of(
                "class Pool:\n"
                "    def limits(self):\n"
                "        return ConcurrencyLimits(groups={'items': self._cap})\n"
            )
        )

    # -- own admission pacing --------------------------------------------------------

    def test_rule_admission_pacing_fires_on_a_token_bucket(self) -> None:
        assert OneSchedulerInventory.paces_its_own_admission(
            self._class_of(
                "class Limiter:\n"
                "    async def acquire(self):\n"
                "        now = time.perf_counter()\n"
                "        wait = self._next_at - now\n"
                "        if wait > 0:\n"
                "            await asyncio.sleep(wait)\n"
            )
        )

    def test_rule_admission_pacing_ignores_measuring_a_latency(self) -> None:
        assert not OneSchedulerInventory.paces_its_own_admission(
            self._class_of(
                "class Timer:\n"
                "    async def measure(self, thunk):\n"
                "        started = time.perf_counter()\n"
                "        value = await thunk()\n"
                "        return value, time.perf_counter() - started\n"
            )
        )
