"""Tool testing kit — reusable doubles and helpers for unit-testing tools.

Public surface:

* :class:`StubTool` — a configurable sync/async/streaming/stateful tool double.
* :class:`ToolTestHarness` — bundles a tool with schema + engine-run assertions;
  its static methods are the tool-agnostic helpers:
  :meth:`~ToolTestHarness.make_stub_tool` (:class:`StubTool` factory),
  :meth:`~ToolTestHarness.assert_tool_schema` /
  :meth:`~ToolTestHarness.assert_tool_schema_shape` (schema assertions),
  :meth:`~ToolTestHarness.run_tool` / :meth:`~ToolTestHarness.collect_tool_stream`
  (drivers; a call runs through the engine).
"""

from __future__ import annotations
