"""Guard: ``pirn_agents`` carries no parallel implementation of a core seam.

The "agents speaks core" ADR (2026-09-13) adds six seams to ``pirn-core`` in
WS0 — retry/timeout, the run-scoped nesting guard, the declared input schema,
admission and its runtime feedback, the ``Check`` role, and the awaitable loop
step — precisely so agents can delete its own versions of them.

There is no allowlist here. The version this replaced froze six inventories of
class *names* by exact equality; every one of them reached empty, and the
re-audit that followed found the shadows this file now reports, living under
names the regexes never mentioned and behind bases the exclusion list never
knew. A name-keyed inventory is emptied by a rename, so each assertion below
is the rule itself — **no class carries this seam's shape** — and
:class:`TestCoreSeamDetectorsFire` proves each detector fires on the shape it
names, so an empty finding means an empty tree and not a blind detector.
"""

from __future__ import annotations

import ast
import unittest

from tests.agents_source_index import AgentsSourceIndex
from tests.core_seams.core_seam_shadow_inventory import CoreSeamShadowInventory


class TestNoClassShadowsACoreSeam(unittest.TestCase):
    """Every WS0 seam is core's. Asserted, not inventoried."""

    def setUp(self) -> None:
        self.found = CoreSeamShadowInventory.discover()

    def _assert_no_shadow(self, seam: str) -> None:
        found = self.found[seam]
        assert found == frozenset(), {
            "seam": CoreSeamShadowInventory.seams()[seam],
            "shadows": sorted(found),
        }

    def test_the_walk_is_not_vacuous(self) -> None:
        """A guard that scans nothing passes for the wrong reason."""
        assert len(AgentsSourceIndex.classes()) >= 500, len(AgentsSourceIndex.classes())

    def test_no_class_bounds_time_or_retries_by_hand(self) -> None:
        self._assert_no_shadow("retry_timeout")

    def test_no_class_keeps_its_own_run_scoped_state(self) -> None:
        self._assert_no_shadow("nesting")

    def test_no_class_derives_its_own_input_schema(self) -> None:
        self._assert_no_shadow("input_schema")

    def test_no_class_caps_or_paces_work_itself(self) -> None:
        self._assert_no_shadow("admission_feedback")

    def test_no_knot_returns_a_bare_verdict_without_being_a_check(self) -> None:
        self._assert_no_shadow("check_role")

    def test_no_class_steps_an_inner_run_from_its_own_loop(self) -> None:
        self._assert_no_shadow("async_loop_step")


class TestCoreSeamDetectorsFire(unittest.TestCase):
    """Each seam detector fires on the shape it names, and not on core's own wiring."""

    @staticmethod
    def _class_of(source: str) -> ast.ClassDef:
        return next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef))

    def _is_shadow(self, seam: str, source: str, subject: type = object) -> bool:
        return CoreSeamShadowInventory.is_shadow(seam, subject, self._class_of(source))

    # -- retry / timeout --------------------------------------------------------

    def test_rule_retry_timeout_fires_on_a_hand_rolled_deadline(self) -> None:
        assert self._is_shadow(
            "retry_timeout",
            "class Runner:\n"
            "    async def run(self, thunk):\n"
            "        return await asyncio.wait_for(thunk(), timeout=self._budget)\n",
        )

    def test_rule_retry_timeout_fires_on_a_renamed_retry_loop(self) -> None:
        """The version this replaced matched the class name ``RetryPolicy``."""
        assert self._is_shadow(
            "retry_timeout",
            "class AttemptDriver:\n"
            "    async def run(self, thunk):\n"
            "        for _attempt in range(self._limit):\n"
            "            try:\n"
            "                return await thunk()\n"
            "            except RuntimeError:\n"
            "                await asyncio.sleep(self._backoff)\n"
            "        raise RuntimeError('exhausted')\n",
        )

    def test_rule_retry_timeout_ignores_a_declared_policy(self) -> None:
        assert not self._is_shadow(
            "retry_timeout",
            "class Caller:\n"
            "    async def process(self, call, **_):\n"
            "        return Inner(call=call, _config=KnotConfig(id='i', retry=self._policy))\n",
        )

    # -- nesting guard ------------------------------------------------------------

    def test_rule_nesting_fires_on_a_private_context_var(self) -> None:
        assert self._is_shadow(
            "nesting",
            "class Depth:\n    _depth = ContextVar('depth', default=0)\n",
        )

    def test_rule_nesting_ignores_reading_the_runs_own_nesting(self) -> None:
        assert not self._is_shadow(
            "nesting",
            "class Depth:\n    def current(self):\n        return RunNesting.current_depth()\n",
        )

    # -- input schema ---------------------------------------------------------------

    def test_rule_input_schema_fires_on_signature_introspection(self) -> None:
        assert self._is_shadow(
            "input_schema",
            "class Deriver:\n"
            "    def schema_for(self, fn):\n"
            "        return {name: p.annotation for name, p in signature(fn).parameters.items()}\n",
        )

    def test_rule_input_schema_fires_on_type_hint_introspection(self) -> None:
        assert self._is_shadow(
            "input_schema",
            "class Deriver:\n    def schema_for(self, fn):\n        return get_type_hints(fn)\n",
        )

    def test_rule_input_schema_ignores_asking_the_knot(self) -> None:
        assert not self._is_shadow(
            "input_schema",
            "class Deriver:\n"
            "    def schema_for(self, knot):\n"
            "        return knot.input_json_schema()\n",
        )

    # -- admission feedback -----------------------------------------------------------

    def test_rule_admission_fires_on_a_private_semaphore(self) -> None:
        assert self._is_shadow(
            "admission_feedback",
            "class Pool:\n    def __init__(self, n):\n        self._slots = asyncio.Semaphore(n)\n",
        )

    def test_rule_admission_fires_on_a_hand_rolled_pacer(self) -> None:
        assert self._is_shadow(
            "admission_feedback",
            "class Pacer:\n"
            "    async def admit(self):\n"
            "        now = time.monotonic()\n"
            "        if now < self._next_at:\n"
            "            await asyncio.sleep(self._next_at - now)\n",
        )

    def test_rule_admission_ignores_declaring_a_group_cap(self) -> None:
        assert not self._is_shadow(
            "admission_feedback",
            "class Pool:\n"
            "    def limits(self):\n"
            "        return ConcurrencyLimits(groups={'tools': self._cap})\n",
        )

    # -- check role ---------------------------------------------------------------------

    def test_rule_check_role_fires_on_a_knot_returning_a_bare_bool(self) -> None:
        from pirn.core.knot import Knot

        class _VerdictKnot(Knot):
            """A knot whose output is a verdict, without being a ``Check``."""

        assert self._is_shadow(
            "check_role",
            "class Verdict:\n"
            "    async def process(self, score, **_) -> bool:\n"
            "        return score > self._threshold\n",
            _VerdictKnot,
        )

    def test_rule_check_role_ignores_a_real_check(self) -> None:
        from pirn.nodes.check import Check

        class _RealCheck(Check):
            """Wired as core's ``Check`` role."""

        assert not self._is_shadow(
            "check_role",
            "class Verdict:\n"
            "    async def process(self, score, **_) -> bool:\n"
            "        return score > self._threshold\n",
            _RealCheck,
        )

    def test_rule_check_role_ignores_a_knot_returning_a_value(self) -> None:
        from pirn.core.knot import Knot

        class _ValueKnot(Knot):
            """A knot whose output is a value, not a verdict."""

        assert not self._is_shadow(
            "check_role",
            "class Scorer:\n"
            "    async def process(self, text, **_) -> float:\n"
            "        return self._score(text)\n",
            _ValueKnot,
        )

    # -- async loop step --------------------------------------------------------------------

    def test_rule_async_loop_step_fires_on_a_run_per_iteration(self) -> None:
        assert self._is_shadow(
            "async_loop_step",
            "class Stepper:\n"
            "    async def process(self, steps, **_):\n"
            "        out = []\n"
            "        for step in steps:\n"
            "            with Tapestry() as inner:\n"
            "                Alpha(step=step, _config=KnotConfig(id='a'))\n"
            "            out.append(await self._run_inner(inner))\n"
            "        return out\n",
        )

    def test_rule_async_loop_step_fires_on_a_loop_built_fan_out(self) -> None:
        """One run, but its nodes declared one at a time from a Python loop."""
        assert self._is_shadow(
            "async_loop_step",
            "class Batcher:\n"
            "    async def process(self, calls, **_):\n"
            "        with Tapestry() as inner:\n"
            "            per_call = {}\n"
            "            for index, call in enumerate(calls):\n"
            "                per_call[f'c{index}'] = self._call_knot(call, index)\n"
            "            Aggregator(_config=KnotConfig(id='results'), **per_call)\n"
            "        run = await self._run_inner(inner)\n"
            "        return run.outputs['results']\n",
        )

    def test_rule_async_loop_step_ignores_a_declared_graph(self) -> None:
        assert not self._is_shadow(
            "async_loop_step",
            "class Pipeline:\n"
            "    async def process(self, question, **_):\n"
            "        retrieve = Retrieve(question=question, _config=KnotConfig(id='r'))\n"
            "        return Answer(context=retrieve, _config=KnotConfig(id='a'))\n",
        )

    def test_rule_async_loop_step_ignores_a_single_inner_run(self) -> None:
        """Resolving one value before building the rest is the sanctioned shape."""
        assert not self._is_shadow(
            "async_loop_step",
            "class Pipeline:\n"
            "    async def process(self, question, **_):\n"
            "        with Tapestry() as inner:\n"
            "            Plan(question=question, _config=KnotConfig(id='p'))\n"
            "        run = await self._run_inner(inner)\n"
            "        return Answer(plan=run.outputs['p'], _config=KnotConfig(id='a'))\n",
        )
