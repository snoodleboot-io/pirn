"""Guard: a ``Knot`` must run its work through the engine, not bypass it inline.

A `SubTapestry` promises the engine's guarantees — a `Result` per knot, run
history, lineage, determinism, replay. It delivers them only if `process()`
*declares an inner graph and returns its sink*. A `process()` that computes the
answer in Python and hands back a knot wrapping the finished value satisfies the
type signature and delivers none of it. The same failure mode has narrower
cousins on any `Knot`: awaiting a tool's `invoke()` or an LLM's `chat()`
directly, fanning calls out with `asyncio.gather` instead of the engine's own
concurrent scheduling, or retrying with a hand-rolled `while True` instead of
`RetryPolicy.run()` — each one produces a value with no lineage row, no
`Ok|Err|Skipped`, and nothing the engine can schedule, cache, or replay.

The two shapes are indistinguishable by inspection, which is the actual problem:
"do the work" and "build a pipeline that does the work" look the same from the
call site. See PIR-731 (the original three checks) and PIR-856 (the four
added here, and the walk widening from "`SubTapestry` under `specializations/`"
to "every `Knot` in `pirn_agents`" — a bypass is a property of `process()`,
not of where the class lives).

`SubTapestry.__call__` already enforces the easy half of the SubTapestry-shaped
bypass at runtime — the sink must be a `Knot`, and must be registered in the
inner tapestry. That check cannot see a closure over a precomputed value,
because a closure over a precomputed value *is* a registered `Knot`. The seven
static checks below cover what runtime enforcement cannot.

## Why this is a ratchet, not a clean assertion

Fixing a bypass is a per-knot design job — WS7 did five, PIR-856 did three
more (`ParallelToolCaller`, `ToolChain`, `ReActStepExecutor`; a fourth,
`ParallelToolExecutor`, is a deliberate deferral: its retry/timeout richness
needs real inter-attempt backoff sleep, which `LoopSubTapestry`'s synchronous
`step`/`fold` contract cannot express without either dropping the backoff or a
core-level change outside this ticket) — so the honest guard is one that
freezes the inventory rather than pretending it is empty.

The allowlists are asserted by **exact equality**, deliberately:

* adding a bypass fails, because the finding is not in the list;
* fixing one *without* updating the list also fails, because the list still
  names it.

The second half is what keeps the list from rotting into a lie. When you fix a
knot, delete its line and watch this test go green.

**Other lanes reduce this inventory concurrently.** Regenerate the allowlists
from the current tree with:

.. code-block:: shell

    python -m tests.specializations.base.regen_bypass_allowlist

run from the package root (``packages/pirn-agents``); paste its output over
the seven constants below.
"""

from __future__ import annotations

import ast
import unittest

from tests.specializations.base.bypass_inventory import BypassInventory

# --- known bypasses, frozen ------------------------------------------------
# Regenerate with: python -m tests.specializations.base.regen_bypass_allowlist

#: `await <child>.process(...)` — runs a child pipeline's body directly instead
#: of wiring it as a knot, so the child contributes no Result and no lineage.
#: PIR-769 fixed four of these in multi_agent/; PIR-856 widened the walk beyond
#: `specializations/` and found one more pre-existing instance under
#: `retrieval/` (`HybridGraphRetriever`, awaiting its `traversal` knot's
#: `process()` directly because a bare `Knot` subclass used as a *value* type
#: made `Knot._build_adapters` raise). PIR-867 fixed it: `traversal` is wired
#: as a genuine upstream parent now. Kept as a `frozenset()` assertion so a
#: future instance regresses loudly.
AWAITS_CHILD_PROCESS: frozenset[str] = frozenset()

#: Returns a `Source` defined inside `process()` that closes over an
#: already-computed value. The engine then "runs" a graph of one knot whose job
#: is to hand back an answer Python already had. Empty: `LatsSearch` was the
#: last member — see `_LatsResultExtractor` (ADR agents-speaks-core WS5b).
#: Kept as an assertion (not deleted) so a future inline `Source` regresses
#: loudly.
RETURNS_INLINE_SOURCE: frozenset[str] = frozenset()

#: `with Tapestry():` opened and never run. Its only effect is to stop the knots
#: built inside it leaking into the outer graph — so those knots are constructed,
#: never executed, and invisible. Empty: `LatsSearch` was the last member — its
#: proposer call now runs through `self._run_inner(...)`, per iteration, like
#: the rest of the package's nested-resolve pipelines (ADR agents-speaks-core
#: WS5b). Kept as an assertion so a future unrun `Tapestry()` regresses loudly.
UNRUN_TAPESTRY: frozenset[str] = frozenset()

#: `await <x>.invoke(...)` awaited directly rather than through a
#: `ToolInvocation` knot. `tools/tool_invocation.py::ToolInvocation` is the one
#: sanctioned entry — it *is* the knot whose job is to make this call. PIR-856
#: fixed three call sites (`ParallelToolCaller`, `ToolChain`,
#: `ReActStepExecutor`); these predate this lane and are out of its scope.
AWAITS_INVOKE = frozenset(
    {
        "specializations/routing/_attempt_tier.py::_AttemptTier",
    }
)

#: `asyncio.gather(...)` used to fan calls out by hand instead of letting the
#: engine schedule N sibling knots concurrently (the `Aggregator` fan-out
#: shape; see `tools/tool_invocation.py`'s module docstring). PIR-867 fixed
#: the three that predated this lane: `HybridRetriever`'s dense/lexical arms
#: and `_ChunkEmbedderStore`'s per-chunk writes are each their own knot wired
#: into an `Aggregator`; `_IngestionRunner`'s per-document ETL is too, with a
#: `ConcurrencyLimits` group cap (`MapAgent`'s lever) replacing the hand-held
#: `asyncio.Semaphore`. Kept as a `frozenset()` assertion so a future
#: instance regresses loudly.
USES_ASYNCIO_GATHER: frozenset[str] = frozenset()

#: A `for`/`while` loop whose body directly awaits an LLM or tool call
#: (`.chat(`, `.complete(`, `.invoke(`, `.search(`) instead of the engine
#: fanning sibling knots out or a `LoopSubTapestry` iterating them. PIR-867
#: fixed the three that remained: `_ChunkTranslator`/`FactClaimVerifier` fan
#: out one knot per independent item into an `Aggregator`; `PlanExecutor`'s
#: steps genuinely depend on prior results, so it wired a `LoopSubTapestry`
#: (`_PlanStepLoop`) instead. Kept as a `frozenset()` assertion so a future
#: instance regresses loudly.
LOOP_AWAITS_LLM_OR_TOOL_CALL: frozenset[str] = frozenset()

#: A literal `while True:` retry loop instead of composing `RetryPolicy.run()`
#: (PIR-856 retrofitted the four `pirn_agents`-owned instances that existed
#: before this ticket; this is what remains).
HAND_ROLLED_WHILE_TRUE_RETRY = frozenset(
    {
        "specializations/conversation/conversation_memory_pruner.py::ConversationMemoryPruner",
    }
)


class TestNoNewEngineBypass(unittest.TestCase):
    """Freeze the bypass inventory. Exact equality in both directions."""

    def setUp(self) -> None:
        self.pipelines = BypassInventory.discover_process_methods()

    def test_the_walk_is_not_vacuous(self) -> None:
        """A guard that finds nothing passes for the wrong reason."""
        assert len(self.pipelines) >= 200, len(self.pipelines)

    def test_awaiting_a_child_process_is_frozen(self) -> None:
        found = {
            label
            for label, proc in self.pipelines.items()
            if BypassInventory.awaits_child_process(proc)
        }
        assert found == AWAITS_CHILD_PROCESS, {
            "new bypasses": sorted(found - AWAITS_CHILD_PROCESS),
            "fixed — remove from AWAITS_CHILD_PROCESS": sorted(AWAITS_CHILD_PROCESS - found),
        }

    def test_returning_an_inline_source_is_frozen(self) -> None:
        found = {
            label
            for label, proc in self.pipelines.items()
            if BypassInventory.returns_inline_source(proc)
        }
        assert found == RETURNS_INLINE_SOURCE, {
            "new bypasses": sorted(found - RETURNS_INLINE_SOURCE),
            "fixed — remove from RETURNS_INLINE_SOURCE": sorted(RETURNS_INLINE_SOURCE - found),
        }

    def test_unrun_tapestries_are_frozen(self) -> None:
        found = {
            label
            for label, proc in self.pipelines.items()
            if BypassInventory.opens_unrun_tapestry(proc)
        }
        assert found == UNRUN_TAPESTRY, {
            "new bypasses": sorted(found - UNRUN_TAPESTRY),
            "fixed — remove from UNRUN_TAPESTRY": sorted(UNRUN_TAPESTRY - found),
        }

    def test_awaiting_invoke_directly_is_frozen(self) -> None:
        found = {
            label for label, proc in self.pipelines.items() if BypassInventory.awaits_invoke(proc)
        }
        assert found == AWAITS_INVOKE, {
            "new bypasses": sorted(found - AWAITS_INVOKE),
            "fixed — remove from AWAITS_INVOKE": sorted(AWAITS_INVOKE - found),
        }

    def test_using_asyncio_gather_is_frozen(self) -> None:
        found = {
            label
            for label, proc in self.pipelines.items()
            if BypassInventory.uses_asyncio_gather(proc)
        }
        assert found == USES_ASYNCIO_GATHER, {
            "new bypasses": sorted(found - USES_ASYNCIO_GATHER),
            "fixed — remove from USES_ASYNCIO_GATHER": sorted(USES_ASYNCIO_GATHER - found),
        }

    def test_looped_llm_or_tool_calls_are_frozen(self) -> None:
        found = {
            label
            for label, proc in self.pipelines.items()
            if BypassInventory.loop_awaits_llm_or_tool_call(proc)
        }
        assert found == LOOP_AWAITS_LLM_OR_TOOL_CALL, {
            "new bypasses": sorted(found - LOOP_AWAITS_LLM_OR_TOOL_CALL),
            "fixed — remove from LOOP_AWAITS_LLM_OR_TOOL_CALL": sorted(
                LOOP_AWAITS_LLM_OR_TOOL_CALL - found
            ),
        }

    def test_hand_rolled_while_true_retries_are_frozen(self) -> None:
        found = {
            label
            for label, proc in self.pipelines.items()
            if BypassInventory.hand_rolled_while_true_retry(proc)
        }
        assert found == HAND_ROLLED_WHILE_TRUE_RETRY, {
            "new bypasses": sorted(found - HAND_ROLLED_WHILE_TRUE_RETRY),
            "fixed — remove from HAND_ROLLED_WHILE_TRUE_RETRY": sorted(
                HAND_ROLLED_WHILE_TRUE_RETRY - found
            ),
        }


class TestDetectorsAreDiscriminating(unittest.TestCase):
    """The detectors must fire on the shapes they name, and not on clean code.

    Without these, an allowlist that matches a detector which silently stopped
    working would still be green — the failure mode a ratchet is most prone to.
    """

    @staticmethod
    def _process_of(source: str) -> ast.AST:
        tree = ast.parse(source)
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        return next(
            n
            for n in cls.body
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == "process"
        )

    CLEAN = """
class P:
    async def process(self, x, **_):
        a = Alpha(value=x, _config=KnotConfig(id="a"))
        return Beta(source=a, _config=KnotConfig(id="b"))
"""

    def test_clean_pipeline_trips_nothing(self) -> None:
        proc = self._process_of(self.CLEAN)
        assert not BypassInventory.awaits_child_process(proc)
        assert not BypassInventory.returns_inline_source(proc)
        assert not BypassInventory.opens_unrun_tapestry(proc)
        assert not BypassInventory.awaits_invoke(proc)
        assert not BypassInventory.uses_asyncio_gather(proc)
        assert not BypassInventory.loop_awaits_llm_or_tool_call(proc)
        assert not BypassInventory.hand_rolled_while_true_retry(proc)

    def test_awaiting_self_process_is_allowed(self) -> None:
        """Recursion into one's own `process` is not a bypass."""
        proc = self._process_of(
            "class P:\n    async def process(self, **_):\n        return await self.process()\n"
        )
        assert not BypassInventory.awaits_child_process(proc)

    def test_awaiting_a_child_trips(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, child, **_):\n"
            "        return await child.process(x=1)\n"
        )
        assert BypassInventory.awaits_child_process(proc)

    def test_returned_inline_source_trips(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, **_):\n"
            "        v = compute()\n"
            "        class _R(Source):\n"
            "            async def process(self, **_):\n"
            "                return v\n"
            "        return _R(_config=KnotConfig(id='r'))\n"
        )
        assert BypassInventory.returns_inline_source(proc)

    def test_inline_source_that_seeds_a_graph_is_allowed(self) -> None:
        """It is the *returned* sink that matters, not the class's existence."""
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, **_):\n"
            "        class _Seed(Source):\n"
            "            async def process(self, **_):\n"
            "                return 0\n"
            "        seed = _Seed(_config=KnotConfig(id='s'))\n"
            "        return Real(state=seed, _config=KnotConfig(id='r'))\n"
        )
        assert not BypassInventory.returns_inline_source(proc)

    def test_unrun_tapestry_trips(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, **_):\n"
            "        with Tapestry():\n"
            "            Alpha(_config=KnotConfig(id='a'))\n"
            "        return Beta(_config=KnotConfig(id='b'))\n"
        )
        assert BypassInventory.opens_unrun_tapestry(proc)

    def test_a_tapestry_passed_to_run_inner_is_allowed(self) -> None:
        """The sanctioned shape: resolve a value, then build the rest from it."""
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, **_):\n"
            "        with Tapestry() as inner:\n"
            "            Alpha(_config=KnotConfig(id='a'))\n"
            "        result = await self._run_inner(inner)\n"
            "        return Beta(v=result.outputs['a'], _config=KnotConfig(id='b'))\n"
        )
        assert not BypassInventory.opens_unrun_tapestry(proc)

    def test_awaiting_invoke_directly_trips(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, tool, call, **_):\n"
            "        result = await tool.invoke(call.arguments)\n"
            "        return result\n"
        )
        assert BypassInventory.awaits_invoke(proc)

    def test_wiring_a_tool_invocation_knot_is_allowed(self) -> None:
        """The sanctioned shape: build the knot, do not call the tool by hand."""
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, tool, call, **_):\n"
            "        return ToolInvocation(tool=tool, call=call, _config=KnotConfig(id='inv'))\n"
        )
        assert not BypassInventory.awaits_invoke(proc)

    def test_asyncio_gather_trips(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, items, **_):\n"
            "        return await asyncio.gather(*(f(i) for i in items))\n"
        )
        assert BypassInventory.uses_asyncio_gather(proc)

    def test_bare_imported_gather_trips(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, items, **_):\n"
            "        return await gather(*(f(i) for i in items))\n"
        )
        assert BypassInventory.uses_asyncio_gather(proc)

    def test_aggregator_fan_out_does_not_trip_gather(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, **kwargs):\n"
            "        return Aggregator(combine=self._merge, _config=KnotConfig(id='agg'), **kwargs)\n"
        )
        assert not BypassInventory.uses_asyncio_gather(proc)

    def test_loop_awaiting_a_tool_call_trips(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, tools, args, **_):\n"
            "        out = []\n"
            "        for tool in tools:\n"
            "            out.append(await tool.invoke(args))\n"
            "        return out\n"
        )
        assert BypassInventory.loop_awaits_llm_or_tool_call(proc)

    def test_loop_awaiting_an_llm_chat_call_trips(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, llm, prompts, **_):\n"
            "        out = []\n"
            "        while prompts:\n"
            "            out.append(await llm.chat(prompts.pop()))\n"
            "        return out\n"
        )
        assert BypassInventory.loop_awaits_llm_or_tool_call(proc)

    def test_loop_building_per_item_knots_is_allowed(self) -> None:
        """Constructing N knots for the engine to fan out is not re-issuing the call."""
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, calls, **_):\n"
            "        per_call = {}\n"
            "        for i, call in enumerate(calls):\n"
            "            per_call[f'c{i}'] = ToolInvocation(tool=call.tool, call=call, _config=KnotConfig(id=f'inv{i}'))\n"
            "        return Aggregator(combine=self._merge, _config=KnotConfig(id='agg'), **per_call)\n"
        )
        assert not BypassInventory.loop_awaits_llm_or_tool_call(proc)

    def test_loop_awaiting_an_unrelated_method_is_allowed(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, items, **_):\n"
            "        out = []\n"
            "        for item in items:\n"
            "            out.append(await item.close())\n"
            "        return out\n"
        )
        assert not BypassInventory.loop_awaits_llm_or_tool_call(proc)

    def test_while_true_retry_trips(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, thunk, **_):\n"
            "        attempt = 0\n"
            "        while True:\n"
            "            try:\n"
            "                return await thunk()\n"
            "            except Exception:\n"
            "                attempt += 1\n"
        )
        assert BypassInventory.hand_rolled_while_true_retry(proc)

    def test_retry_policy_run_does_not_trip_while_true(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, thunk, policy, **_):\n"
            "        return await policy.run(thunk)\n"
        )
        assert not BypassInventory.hand_rolled_while_true_retry(proc)

    def test_a_bounded_while_loop_does_not_trip_while_true(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, items, **_):\n"
            "        i = 0\n"
            "        while i < len(items):\n"
            "            i += 1\n"
            "        return i\n"
        )
        assert not BypassInventory.hand_rolled_while_true_retry(proc)
