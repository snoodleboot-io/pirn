"""``BaseTool`` — deprecated alias of :class:`~pirn_agents.tools.tool.Tool` (one cycle).

Before the ADR "agents speaks core" (WS1) the base-library tools shared this
subclass for two conveniences: ``as_tool_result`` (invoke and wrap in a
``ToolResult``) and ``_string_argument`` (the ReAct ``"input"`` alias).  Both
now live where the knot model puts them — the ``ToolResult`` view is built by
:meth:`ToolResult.from_result` from a call knot's ``Result`` and the alias is
resolved by :meth:`ToolFactory.resolve_arguments` — and every base tool is a
plain :class:`Tool`.  ``BaseTool`` stays importable as a thin subclass so an
external subclass keeps its base; it adds nothing and warns on subclassing.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall

if TYPE_CHECKING:
    from pirn_agents.tools.tool_result import ToolResult


class BaseTool(Tool):
    """Deprecated: subclass :class:`Tool` directly."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        warnings.warn(
            f"{cls.__qualname__} subclasses BaseTool, which is deprecated (ADR agents-speaks-core "
            "WS1): subclass pirn_agents.tools.tool.Tool directly",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init_subclass__(**kwargs)

    @classmethod
    async def as_tool_result(cls, call: ToolCall) -> ToolResult:
        """Deprecated: run ``call`` outside the engine and return the ``ToolResult`` view."""
        return await cls.factory().as_tool_result(call)

    @staticmethod
    def _require_mapping(tool_name: str, arguments: Mapping[str, Any]) -> None:
        """Raise :class:`TypeError` unless ``arguments`` is a mapping."""
        if not isinstance(arguments, Mapping):
            raise TypeError(
                f"{tool_name}.invoke: arguments must be a Mapping, got {type(arguments).__name__}"
            )

    @staticmethod
    def _string_argument(
        tool_name: str,
        arguments: Mapping[str, Any],
        name: str,
        *,
        allow_empty: bool = False,
    ) -> str:
        """Return the string argument ``name``, falling back to ``"input"``.

        Kept for external ``invoke``-shaped subclasses; a knot-shaped tool
        declares ``name`` as a ``process()`` input and lets
        :meth:`ToolFactory.resolve_arguments` handle the alias.

        Raises:
            ValueError: If neither ``name`` nor ``"input"`` yields a string (or the
                value is empty and ``allow_empty`` is ``False``).
        """
        value = arguments.get(name)
        if value is None:
            value = arguments.get("input")
        if not isinstance(value, str) or (not allow_empty and not value):
            raise ValueError(
                f"{tool_name}.invoke: {name!r} must be a non-empty string, got {value!r}"
            )
        return value
