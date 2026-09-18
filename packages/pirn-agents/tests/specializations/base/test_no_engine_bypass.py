"""Guard: a ``Knot`` runs its work through the engine, never inline.

A ``Knot`` promises an ``Ok | Err | Skipped`` per call, a lineage row,
determinism, replay, scheduling and cancellation — for work the engine runs.
Work the knot does itself gets none of it, while still type-checking: "do the
work" and "declare a graph that does the work" look identical from the call
site, which is the whole problem.

There is no allowlist here, and there is nothing to regenerate. The previous
version froze seven inventories of known bypasses by exact equality and shipped
a script that recomputed them from the current tree — which made every new
bypass self-approving, and (because all seven keyed on names: ``process``,
``chat``, ``complete``, ``invoke``, ``search``, ``while True``) let every
bypass written with different names through while the ratchet stayed green.
A repository-wide re-audit found the bypasses these assertions now report.

Each assertion below is therefore the rule itself: **no knot carries this
shape**. A knot that does fails here until it is fixed, never until it is
listed. :class:`TestBypassDetectorsFire` proves each detector fires on the
shape it names, so an empty finding means an empty tree and not a blind
detector.
"""

from __future__ import annotations

import ast
import unittest

from tests.agents_source_index import AgentsSourceIndex
from tests.specializations.base.bypass_inventory import BypassInventory


class TestNoKnotBypassesTheEngine(unittest.TestCase):
    """Every knot's work goes through the engine. Asserted, not inventoried."""

    def setUp(self) -> None:
        self.found = BypassInventory.discover()

    def test_the_walk_is_not_vacuous(self) -> None:
        """A guard that scans nothing passes for the wrong reason."""
        assert len(AgentsSourceIndex.knots()) >= 200, len(AgentsSourceIndex.knots())

    def test_no_knot_awaits_a_collaborator_in_a_loop_or_fan_out(self) -> None:
        found = self.found["collaborator_await_out_of_band"]
        assert found == frozenset(), sorted(found)

    def test_no_knot_bounds_time_or_retries_by_hand(self) -> None:
        found = self.found["hand_rolled_time_bound_or_retry"]
        assert found == frozenset(), sorted(found)

    def test_no_knot_holds_its_own_concurrency_budget(self) -> None:
        found = self.found["own_concurrency_budget"]
        assert found == frozenset(), sorted(found)

    def test_no_knot_paces_itself_by_a_clock(self) -> None:
        found = self.found["clock_pacing"]
        assert found == frozenset(), sorted(found)


class TestBypassDetectorsFire(unittest.TestCase):
    """Each detector fires on the shape it names, and not on the engine's own shapes.

    A rule that finds nothing because it *can* find nothing is the failure
    mode a ratchet is most prone to, so every rule above is pinned here
    against a synthetic knot that carries the shape and one that does not.
    """

    @staticmethod
    def _class_of(source: str) -> ast.ClassDef:
        return next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef))

    _clean = """
class CleanPipeline:
    async def process(self, calls, **_):
        per_call = {}
        for index, call in enumerate(calls):
            per_call[f"c{index}"] = ToolInvocation(call=call, _config=KnotConfig(id=f"i{index}"))
        return Aggregator(combine=self._merge, _config=KnotConfig(id="agg"), **per_call)
"""

    def test_a_knot_that_declares_a_graph_trips_nothing(self) -> None:
        node = self._class_of(self._clean)
        assert not BypassInventory.awaits_collaborator_out_of_band(node)
        assert not BypassInventory.bounds_or_retries_by_hand(node)
        assert not BypassInventory.holds_own_concurrency_budget(node)
        assert not BypassInventory.paces_itself_by_clock(node)

    # -- collaborator await out of band --------------------------------------

    def test_rule_collaborator_await_fires_on_a_loop_that_awaits_a_store(self) -> None:
        """The shape the name-keyed version missed entirely: ``store``, not ``chat``."""
        node = self._class_of(
            "class W:\n"
            "    async def process(self, store, facts, **_):\n"
            "        for fact in facts:\n"
            "            await store.store(fact.key, fact.payload)\n"
            "        return len(facts)\n"
        )
        assert BypassInventory.awaits_collaborator_out_of_band(node)

    def test_rule_collaborator_await_fires_outside_process_too(self) -> None:
        """Moving the loop into a helper does not launder it."""
        node = self._class_of(
            "class W:\n"
            "    async def process(self, store, keys, **_):\n"
            "        return await self._load_all(store, keys)\n"
            "    async def _load_all(self, store, keys):\n"
            "        out = []\n"
            "        for key in keys:\n"
            "            out.append(await store.retrieve(key))\n"
            "        return out\n"
        )
        assert BypassInventory.awaits_collaborator_out_of_band(node)

    def test_rule_collaborator_await_fires_on_a_gather_of_collaborator_calls(self) -> None:
        node = self._class_of(
            "class W:\n"
            "    async def process(self, store, keys, **_):\n"
            "        return await asyncio.gather(store.get(keys[0]), store.get(keys[1]))\n"
        )
        assert BypassInventory.awaits_collaborator_out_of_band(node)

    def test_rule_collaborator_await_ignores_a_loop_building_per_item_knots(self) -> None:
        """Declaring N knots for the engine to run is the sanctioned shape."""
        node = self._class_of(self._clean)
        assert not BypassInventory.awaits_collaborator_out_of_band(node)

    def test_rule_collaborator_await_ignores_a_single_awaited_call(self) -> None:
        """One call, awaited once, is not a hand-rolled fan-out."""
        node = self._class_of(
            "class W:\n"
            "    async def process(self, store, key, **_):\n"
            "        return await store.retrieve(key)\n"
        )
        assert not BypassInventory.awaits_collaborator_out_of_band(node)

    # -- hand-rolled time bound / retry ---------------------------------------

    def test_rule_time_bound_fires_on_a_hand_rolled_wait_for(self) -> None:
        node = self._class_of(
            "class W:\n"
            "    async def process(self, thunk, **_):\n"
            "        return await asyncio.wait_for(thunk(), timeout=5)\n"
        )
        assert BypassInventory.bounds_or_retries_by_hand(node)

    def test_rule_retry_fires_on_a_loop_that_swallows_and_goes_round_again(self) -> None:
        node = self._class_of(
            "class W:\n"
            "    async def process(self, thunk, **_):\n"
            "        for _attempt in range(3):\n"
            "            try:\n"
            "                return await thunk()\n"
            "            except RuntimeError:\n"
            "                pass\n"
            "        return None\n"
        )
        assert BypassInventory.bounds_or_retries_by_hand(node)

    def test_rule_retry_fires_on_a_while_loop_retry_without_the_word_true(self) -> None:
        """The version this replaced matched the literal ``while True:`` only."""
        node = self._class_of(
            "class W:\n"
            "    async def process(self, thunk, **_):\n"
            "        remaining = 3\n"
            "        while remaining:\n"
            "            try:\n"
            "                return await thunk()\n"
            "            except RuntimeError:\n"
            "                remaining -= 1\n"
            "        return None\n"
        )
        assert BypassInventory.bounds_or_retries_by_hand(node)

    def test_rule_retry_ignores_a_loop_that_skips_bad_items(self) -> None:
        node = self._class_of(
            "class W:\n"
            "    async def process(self, items, **_):\n"
            "        out = []\n"
            "        for item in items:\n"
            "            try:\n"
            "                out.append(parse(item))\n"
            "            except ValueError:\n"
            "                continue\n"
            "        return out\n"
        )
        assert not BypassInventory.bounds_or_retries_by_hand(node)

    def test_rule_time_bound_ignores_a_declared_knot_timeout(self) -> None:
        node = self._class_of(
            "class W:\n"
            "    async def process(self, call, **_):\n"
            "        return Inner(call=call, _config=KnotConfig(id='i', timeout=5.0))\n"
        )
        assert not BypassInventory.bounds_or_retries_by_hand(node)

    # -- own concurrency budget ------------------------------------------------

    def test_rule_concurrency_budget_fires_on_a_private_semaphore(self) -> None:
        node = self._class_of(
            "class W:\n    def __init__(self, n):\n        self._gate = asyncio.Semaphore(n)\n"
        )
        assert BypassInventory.holds_own_concurrency_budget(node)

    def test_rule_concurrency_budget_fires_on_a_renamed_semaphore(self) -> None:
        node = self._class_of(
            "class W:\n    def _pool(self, key):\n        return BackpressureSemaphore(key)\n"
        )
        assert BypassInventory.holds_own_concurrency_budget(node)

    def test_rule_concurrency_budget_ignores_the_engines_group_cap(self) -> None:
        node = self._class_of(
            "class W:\n"
            "    def limits(self):\n"
            "        return ConcurrencyLimits(groups={'tools': 8})\n"
        )
        assert not BypassInventory.holds_own_concurrency_budget(node)

    # -- clock pacing ------------------------------------------------------------

    def test_rule_clock_pacing_fires_on_a_hand_rolled_token_bucket(self) -> None:
        node = self._class_of(
            "class W:\n"
            "    async def _admit(self):\n"
            "        now = time.monotonic()\n"
            "        if now < self._next_at:\n"
            "            await asyncio.sleep(self._next_at - now)\n"
        )
        assert BypassInventory.paces_itself_by_clock(node)

    def test_rule_clock_pacing_ignores_reading_a_clock_to_record_latency(self) -> None:
        node = self._class_of(
            "class W:\n"
            "    async def process(self, thunk, **_):\n"
            "        started = time.monotonic()\n"
            "        value = await thunk()\n"
            "        return value, time.monotonic() - started\n"
        )
        assert not BypassInventory.paces_itself_by_clock(node)
