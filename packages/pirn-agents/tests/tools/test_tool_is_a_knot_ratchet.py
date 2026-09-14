"""Ratchet: freeze what the "a tool is a Knot" collapse burns down (ADR WS1).

ADR "agents speaks core" (2026-09-13), target model item 1: ``Tool`` becomes a
``Knot`` class — the capability is the class, one call is an instance with
``KnotConfig(id=call_id)``, the outcome is the engine's ``Result`` + lineage.
Until then three parallel things exist in ``pirn_agents`` and are what this
ratchet inventories (see ``tests/tools/tool_knot_inventory.py``):

* classes carrying an ``invoke`` method — a second execution verb beside
  ``Knot.process()``;
* modules importing the parallel vocabulary (``ToolStatus``,
  ``ToolSchemaCompiler``, ``ArgumentValidator`` — all deleted);
* call sites that ``await <x>.invoke(...)`` instead of wiring a knot.

The allowlists are asserted by **exact equality**, deliberately:

* adding a new instance fails, because the finding is not in the list;
* fixing one *without* updating the list also fails, because the list still
  names it.

The second half is what keeps the list from rotting into a lie.  When you
migrate a class or a call site, delete its line and watch this test go green.
Regenerate all three constants with::

    python -c "from tests.tools.tool_knot_inventory import ToolKnotInventory; \\
               print(ToolKnotInventory.render())"

from the package root (``packages/pirn-agents``).

Two families the ``invoke`` inventory used to hold were not tools at all, and
both are gone (PIR-872).  The run-recorder ``invoke(key=, thunk=)`` seam
(``CassetteRecorder``, ``RunRecorder``, ``NullRunRecorder``,
``CassetteRunRecorder``) is deleted: an eval item is a knot, so core
``RunHistory``/``ReplaySession`` record and replay it, and ``ToolTestHarness``
drives a tool through the engine instead of an ``invoke`` method, so
``INVOKE_CLASSES`` is empty.  ``CascadeTier.invoke`` is gone too: a cascade tier
is a model call run as an ``LLMChatCall`` knot, so its ``_TierInvocation`` call
site left this inventory, and ``AWAITED_INVOKE_CALL_SITES`` is empty.
"""

from __future__ import annotations

import ast
import unittest

from tests.tools.tool_knot_inventory import ToolKnotInventory

# --- known inventory, frozen (ADR agents-speaks-core, WS1) -----------------

INVOKE_CLASSES: frozenset[str] = frozenset()

# ToolStatus is deleted and ToolResult/AgentTool are the composed shapes, not
# parallel ones (PIR-872; see ToolKnotInventory.PARALLEL_NAMES). Empty, not
# deleted: importing a reintroduced parallel name fails here.
PARALLEL_VOCABULARY_IMPORTERS: frozenset[str] = frozenset()

AWAITED_INVOKE_CALL_SITES: frozenset[str] = frozenset()


class TestToolKnotInventoryIsFrozen(unittest.TestCase):
    """Freeze the inventory.  Exact equality in both directions."""

    def setUp(self) -> None:
        self.found = ToolKnotInventory.discover()

    def _assert_frozen(self, key: str, expected: frozenset[str], constant: str) -> None:
        found = self.found[key]
        assert found == expected, {
            "new instances": sorted(found - expected),
            f"migrated — remove from {constant}": sorted(expected - found),
        }

    def test_the_walk_is_not_vacuous(self) -> None:
        """A guard that finds nothing passes for the wrong reason.

        PIR-872 emptied all three inventories, so their sizes can no longer
        show the walk ran: assert instead that it parsed the package (the
        detectors themselves are pinned by ``TestDetectorsAreDiscriminating``).
        """
        assert set(self.found) == {"invoke_classes", "importers", "call_sites"}, self.found
        modules = ToolKnotInventory.modules()
        assert len(modules) >= 500, len(modules)

    def test_classes_with_an_invoke_method_are_frozen(self) -> None:
        self._assert_frozen("invoke_classes", INVOKE_CLASSES, "INVOKE_CLASSES")

    def test_parallel_vocabulary_importers_are_frozen(self) -> None:
        self._assert_frozen(
            "importers", PARALLEL_VOCABULARY_IMPORTERS, "PARALLEL_VOCABULARY_IMPORTERS"
        )

    def test_awaited_invoke_call_sites_are_frozen(self) -> None:
        self._assert_frozen("call_sites", AWAITED_INVOKE_CALL_SITES, "AWAITED_INVOKE_CALL_SITES")


class TestDetectorsAreDiscriminating(unittest.TestCase):
    """The detectors must fire on the shapes they name, and not on clean code."""

    @staticmethod
    def _class_of(source: str) -> ast.ClassDef:
        tree = ast.parse(source)
        return next(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef))

    def test_invoke_method_trips(self) -> None:
        node = self._class_of("class T:\n    async def invoke(self, arguments):\n        pass\n")
        assert ToolKnotInventory.defines_invoke(node)

    def test_process_method_does_not_trip(self) -> None:
        node = self._class_of("class T:\n    async def process(self, x, **_):\n        pass\n")
        assert not ToolKnotInventory.defines_invoke(node)

    def test_inherited_invoke_does_not_trip(self) -> None:
        """Only a body of its own counts; a subclass that adds nothing is not a shadow."""
        node = self._class_of("class T(Base):\n    pass\n")
        assert not ToolKnotInventory.defines_invoke(node)

    def test_parallel_import_trips(self) -> None:
        tree = ast.parse("from pirn_agents.tools.tool_status import ToolStatus\n")
        assert ToolKnotInventory.imports_parallel_name(tree) == frozenset({"ToolStatus"})

    def test_composed_tool_result_import_does_not_trip(self) -> None:
        tree = ast.parse("from pirn_agents.tools.tool_result import ToolResult\n")
        assert ToolKnotInventory.imports_parallel_name(tree) == frozenset()

    def test_core_result_import_does_not_trip(self) -> None:
        tree = ast.parse("from pirn.core.ok import Ok\nfrom pirn.core.err import Err\n")
        assert ToolKnotInventory.imports_parallel_name(tree) == frozenset()

    def test_awaited_invoke_trips_with_its_qualname(self) -> None:
        tree = ast.parse(
            "class P:\n"
            "    async def process(self, tool, call, **_):\n"
            "        return await tool.invoke(call.arguments)\n"
        )
        assert ToolKnotInventory.awaited_invoke_sites(tree) == {"P.process"}

    def test_nested_function_site_is_named_by_its_full_path(self) -> None:
        tree = ast.parse(
            "class P:\n"
            "    async def run(self, tool):\n"
            "        async def inner():\n"
            "            return await tool.invoke({})\n"
            "        return inner\n"
        )
        assert ToolKnotInventory.awaited_invoke_sites(tree) == {"P.run.inner"}

    def test_wiring_a_knot_does_not_trip(self) -> None:
        tree = ast.parse(
            "class P:\n"
            "    async def process(self, tool, call, **_):\n"
            "        return ToolInvocation(tool=tool, call=call, _config=KnotConfig(id='i'))\n"
        )
        assert ToolKnotInventory.awaited_invoke_sites(tree) == set()

    def test_un_awaited_invoke_does_not_trip(self) -> None:
        """A sync ``.invoke(`` (e.g. a stream factory) is not the awaited execution verb."""
        tree = ast.parse("def f(tool):\n    return tool.invoke({})\n")
        assert ToolKnotInventory.awaited_invoke_sites(tree) == set()
