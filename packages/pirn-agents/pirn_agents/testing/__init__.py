"""Tool testing kit — reusable doubles and helpers for unit-testing tools.

Public surface:

* :class:`StubTool` — a configurable sync/async/streaming/stateful tool double.
* :class:`ToolTestHarness` — bundles a tool with schema + invocation assertions.
* :meth:`~pirn_agents.testing.tool_test_harness.ToolTestHarness.assert_tool_schema` / :meth:`~pirn_agents.testing.tool_test_harness.ToolTestHarness.assert_tool_schema_shape` — schema assertions.
* :meth:`~pirn_agents.testing.tool_test_harness.ToolTestHarness.invoke_tool` / :meth:`~pirn_agents.testing.tool_test_harness.ToolTestHarness.collect_tool_stream` — invocation drivers.
"""

from __future__ import annotations
