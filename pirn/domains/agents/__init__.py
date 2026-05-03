"""Agentic Pipelines / Patterns knot library.

Install with::

    pip install 'pirn[agents]'

The agents domain has no heavy core dependencies — concrete LLM, memory,
and tool providers are user-supplied through interfaces defined in this
domain.

See ``planning/current/domain-knot-libraries-prd.md`` for the full catalog.
"""

from pirn.domains.agents.tool_decorator import FunctionTool, tool

__all__ = ["tool", "FunctionTool"]
