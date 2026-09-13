"""Ratchet: freeze what the "a tool is a Knot" collapse burns down (ADR WS1).

ADR "agents speaks core" (2026-09-13), target model item 1: ``Tool`` becomes a
``Knot`` class — the capability is the class, one call is an instance with
``KnotConfig(id=call_id)``, the outcome is the engine's ``Result`` + lineage.
Until then three parallel things exist in ``pirn_agents`` and are what this
ratchet inventories (see ``tests/tools/tool_knot_inventory.py``):

* classes carrying an ``invoke`` method — a second execution verb beside
  ``Knot.process()``;
* modules importing the parallel vocabulary (``ToolResult``, ``ToolStatus``,
  ``ToolSchemaCompiler``, ``ArgumentValidator``, ``AgentTool``);
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

Two families in the ``invoke`` inventory are not tools at all and are frozen
here only because the detector is deliberately blunt: the run-recorder
``invoke(key=, thunk=)`` seam (``determinism/``, ``evaluation/``) and the
``CascadeTier.invoke`` provider callable ``_AttemptTier`` awaits.  They belong
to other workstreams and are listed, not migrated, by WS1.
"""

from __future__ import annotations

import ast
import unittest

from tests.tools.tool_knot_inventory import ToolKnotInventory

# --- known inventory, frozen (ADR agents-speaks-core, WS1) -----------------

INVOKE_CLASSES = frozenset(
    {
        "agent/agent_invoker.py::AgentInvoker",
        "determinism/cassette_recorder.py::CassetteRecorder",
        "evaluation/cassette_run_recorder.py::CassetteRunRecorder",
        "evaluation/null_run_recorder.py::NullRunRecorder",
        "evaluation/run_recorder.py::RunRecorder",
        "mcp/mcp_tool.py::McpTool",
        "specializations/structured_output/_extraction_tool.py::_ExtractionTool",
        "testing/stub_tool.py::StubTool",
        "testing/tool_test_harness.py::ToolTestHarness",
        "tools/agent_tool.py::AgentTool",
        "tools/calculator/calculator_tool.py::CalculatorTool",
        "tools/filesystem/glob_tool.py::GlobTool",
        "tools/filesystem/list_dir_tool.py::ListDirTool",
        "tools/filesystem/read_file_tool.py::ReadFileTool",
        "tools/filesystem/write_file_tool.py::WriteFileTool",
        "tools/function_tool.py::FunctionTool",
        "tools/retrieval/rag_tool.py::RagTool",
        "tools/retrieval/retriever_tool.py::RetrieverTool",
        "tools/sandbox/python_exec_tool.py::PythonExecTool",
        "tools/sandbox/shell_tool.py::ShellTool",
        "tools/sql/sql_query_tool.py::SqlQueryTool",
        "tools/tool.py::Tool",
        "tools/web/html_to_text_tool.py::HtmlToTextTool",
        "tools/web/http_request_tool.py::HttpRequestTool",
        "tools/web/web_search_tool.py::WebSearchTool",
    }
)

PARALLEL_VOCABULARY_IMPORTERS = frozenset(
    {
        "agent/_fanout_runner.py",
        "agent/agent_invoker.py",
        "agent/agent_response_mapper.py",
        "agent/agent_schema_deriver.py",
        "agent/parallel_tool_executor.py",
        "mcp/mcp_tool.py",
        "observability/span_emitting_tool_invocation_hook.py",
        "planning/tool_executor.py",
        "planning/tool_result_aggregator.py",
        "specializations/multi_agent/_assemble_orchestrator_workers_result.py",
        "specializations/multi_agent/_worker_invocation.py",
        "specializations/multi_agent/worker_task_result.py",
        "specializations/rag/_agentic_rag_loop.py",
        "specializations/rag/_fallback_document.py",
        "specializations/rag/_follow_up_decision.py",
        "specializations/react/react_step_executor.py",
        "specializations/rewoo/rewoo_result.py",
        "specializations/rewoo/rewoo_synthesizer.py",
        "specializations/routing/_fallback_chain_state.py",
        "specializations/routing/_fold_candidate_result.py",
        "specializations/routing/fallback_result.py",
        "specializations/tool_use/parallel_tool_caller.py",
        "specializations/tool_use/tool_chain.py",
        "specializations/tool_use/tool_result_formatter.py",
        "tools/agent_as_tool_mixin.py",
        "tools/agent_tool.py",
        "tools/as_tool.py",
        "tools/base_tool.py",
        "tools/tool_call_codec.py",
        "tools/tool_decorator.py",
        "tools/tool_invocation.py",
        "tools/tool_invocation_hook.py",
        "tools/tool_result.py",
        "types/content/tool_result_block.py",
        "validation/argument_validator.py",
    }
)

AWAITED_INVOKE_CALL_SITES = frozenset(
    {
        "evaluation/cassette_run_recorder.py::CassetteRunRecorder.invoke",
        "evaluation/run_eval.py::RunEval.run._run_item",
        "specializations/multi_agent/_worker_invocation.py::_WorkerInvocation.process",
        "specializations/routing/_attempt_tier.py::_AttemptTier.process",
        "testing/tool_test_harness.py::ToolTestHarness._invoke_tool",
        "testing/tool_test_harness.py::ToolTestHarness.assert_invokes_to",
        "tools/agent_tool.py::AgentTool.invoke",
        "tools/base_tool.py::BaseTool.as_tool_result",
        "tools/tool_invocation.py::ToolInvocation.process",
    }
)


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
        """A guard that finds nothing passes for the wrong reason."""
        total = sum(len(labels) for labels in self.found.values())
        assert total >= 10, self.found

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
        tree = ast.parse("from pirn_agents.tools.tool_result import ToolResult\n")
        assert ToolKnotInventory.imports_parallel_name(tree) == frozenset({"ToolResult"})

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
