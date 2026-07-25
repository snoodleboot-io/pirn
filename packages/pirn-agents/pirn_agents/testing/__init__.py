"""Tool testing kit — reusable doubles and helpers for unit-testing tools.

Public surface:

* :class:`StubTool` — a configurable sync/async/streaming/stateful tool double.
* :class:`ToolTestHarness` — bundles a tool with schema + invocation assertions.
* :func:`make_stub_tool` — :class:`StubTool` factory.
* :func:`assert_tool_schema` / :func:`assert_schema_shape` — schema assertions.
* :func:`invoke_tool` / :func:`collect_tool_stream` — invocation drivers.
"""

from __future__ import annotations
