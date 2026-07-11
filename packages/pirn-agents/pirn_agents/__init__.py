"""Agentic Pipelines / Patterns knot library.

Install with::

    pip install pirn-agents

The agents domain has no heavy core dependencies — concrete LLM, memory,
and tool providers are user-supplied through interfaces defined in this
domain. Importing this package self-registers every ``Knot`` subclass in
the tree with the shared registry via
``sweet_tea.registry.Registry.fill_registry()`` so the knots become
resolvable by name through
:class:`sweet_tea.abstract_inverter_factory.AbstractInverterFactory`.

See ``planning/current/domain-knot-libraries-prd.md`` for the full catalog.
"""

import warnings

from sweet_tea.registry import Registry
from sweet_tea.sweet_tea_warning import SweetTeaWarning

from pirn_agents.approval_hook import ApprovalHook, authorize_tool_call
from pirn_agents.capability_probe import available_extras
from pirn_agents.permissioned_tool import PermissionedTool, requires_approval
from pirn_agents.stateful_tool import StatefulTool, supports_state
from pirn_agents.streaming_tool import StreamingTool, collect_stream, supports_streaming
from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.testing.tool_test_harness import ToolTestHarness, make_stub_tool
from pirn_agents.tool_decorator import FunctionTool, tool
from pirn_agents.tool_permissions import ToolPermissions
from pirn_agents.tool_registry import ToolRegistry
from pirn_agents.toolset import Toolset

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SweetTeaWarning)
    Registry.fill_registry(module=__name__, library="pirn")

__all__ = [
    "ApprovalHook",
    "FunctionTool",
    "PermissionedTool",
    "StatefulTool",
    "StreamingTool",
    "StubTool",
    "ToolPermissions",
    "ToolRegistry",
    "ToolTestHarness",
    "Toolset",
    "authorize_tool_call",
    "available_extras",
    "collect_stream",
    "make_stub_tool",
    "requires_approval",
    "supports_state",
    "supports_streaming",
    "tool",
]
