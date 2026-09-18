"""Guard: a knot has one execution verb, and the engine runs it (ADR WS1).

ADR "agents speaks core" (2026-09-13), target model item 1: ``Tool`` is a
``Knot`` class — the capability is the class, one call is an instance with
``KnotConfig(id=call_id)``, the outcome is the engine's ``Result`` plus lineage.
A second public coroutine that does work is a way to call the capability the
engine never sees, so it gets no ``Ok | Err | Skipped``, no lineage row, no
retry, timeout, admission, cancellation or replay.

There is no allowlist and nothing to regenerate. The version this replaced froze
three inventories by exact equality — methods named ``invoke``, importers of
three deleted vocabulary names, ``await <x>.invoke(...)`` call sites — and
shipped a ``render()`` that recomputed them from the current tree, which made
every new instance self-approving. All three keyed on the single name ``invoke``,
so renaming it emptied the whole ratchet at once. The assertion below is the
rule itself: **no knot carries a public coroutine beside ``process()`` that does
work**. :class:`TestSecondVerbDetectorFires` proves the detector fires, so an
empty finding means an empty tree and not a blind detector.
"""

from __future__ import annotations

import ast
import unittest

from tests.agents_source_index import AgentsSourceIndex
from tests.tools.tool_knot_inventory import ToolKnotInventory


class TestAKnotHasOneExecutionVerb(unittest.TestCase):
    """``process()`` is the only verb. Asserted, not inventoried."""

    def test_the_walk_is_not_vacuous(self) -> None:
        """A guard that scans nothing passes for the wrong reason."""
        assert len(AgentsSourceIndex.knots()) >= 200, len(AgentsSourceIndex.knots())

    def test_no_knot_carries_a_second_execution_verb(self) -> None:
        found = ToolKnotInventory.discover()
        assert found == {}, {label: sorted(verbs) for label, verbs in found.items()}


class TestSecondVerbDetectorFires(unittest.TestCase):
    """The detector fires on the shape it names, and not on core's own vocabulary."""

    @staticmethod
    def _verbs(source: str, overrides: frozenset[str] = frozenset()) -> frozenset[str]:
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef))
        return ToolKnotInventory.second_execution_verbs(node, overrides)

    def test_rule_fires_on_a_verb_named_invoke(self) -> None:
        assert self._verbs(
            "class Tool:\n"
            "    async def invoke(self, arguments):\n"
            "        return await self._backend.call(arguments)\n"
        ) == frozenset({"invoke"})

    def test_rule_fires_on_a_verb_renamed_away_from_invoke(self) -> None:
        """The failure mode of the version this replaced: rename, ratchet empties."""
        assert self._verbs(
            "class Tool:\n"
            "    async def execute(self, arguments):\n"
            "        return await self._backend.call(arguments)\n"
        ) == frozenset({"execute"})

    def test_rule_fires_through_a_private_helper(self) -> None:
        """Hiding the collaborator behind a helper does not make the verb passive."""
        assert self._verbs(
            "class Tool:\n"
            "    async def run(self, arguments):\n"
            "        return await self._call(arguments)\n"
            "    async def _call(self, arguments):\n"
            "        return await self._backend.call(arguments)\n"
        ) == frozenset({"run"})

    def test_rule_ignores_process_itself(self) -> None:
        assert (
            self._verbs(
                "class Tool:\n"
                "    async def process(self, arguments, **_):\n"
                "        return await self._backend.call(arguments)\n"
            )
            == frozenset()
        )

    def test_rule_ignores_an_override_of_a_core_seam(self) -> None:
        """``LoopSubTapestry.astep`` is core's vocabulary, not a second verb."""
        assert (
            self._verbs(
                "class Loop:\n"
                "    async def astep(self, state):\n"
                "        return await self._advance(state)\n"
                "    async def _advance(self, state):\n"
                "        return await self._llm.chat(state)\n",
                frozenset({"astep"}),
            )
            == frozenset()
        )

    def test_rule_ignores_a_private_coroutine(self) -> None:
        assert (
            self._verbs(
                "class Tool:\n"
                "    async def process(self, arguments, **_):\n"
                "        return await self._call(arguments)\n"
                "    async def _call(self, arguments):\n"
                "        return await self._backend.call(arguments)\n"
            )
            == frozenset()
        )

    def test_rule_ignores_a_public_coroutine_that_does_no_work(self) -> None:
        """A pure accessor is not an execution verb."""
        assert (
            self._verbs(
                "class Tool:\n    async def describe(self):\n        return self._description\n"
            )
            == frozenset()
        )
