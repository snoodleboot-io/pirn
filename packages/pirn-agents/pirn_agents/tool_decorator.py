"""``@tool`` decorator — convert a plain function into a rich :class:`Tool`.

Basic usage stays a one-liner::

    from pirn_agents.tool_decorator import tool

    @tool
    async def web_search(query: str, max_results: int = 5) -> str:
        \"\"\"Search the web and return a summary of the top results.\"\"\"
        ...  # your implementation

    # web_search is now a Tool: name="web_search", description from the
    # docstring, parameters_schema derived from the type hints.

Sync functions are accepted too — :meth:`~pirn_agents.function_tool.FunctionTool.invoke`
wraps them in ``asyncio.to_thread`` automatically.

The decorator also has a **rich, parametrised form** that stays fully backward
compatible with the bare ``@tool`` above::

    from pydantic import BaseModel, Field

    class SearchArgs(BaseModel):
        query: str = Field(description="the search query")
        max_results: int = 5

    @tool(args_model=SearchArgs, scope="web:read", cost_hint=1.0)
    async def web_search(args: SearchArgs) -> list[str]:
        \"\"\"Search the web.\"\"\"
        ...

* ``args_model`` — a pydantic model or dataclass whose JSON schema becomes the
  tool's ``parameters_schema``; incoming arguments are validated/coerced through
  it and the validated object is passed to the function.
* Return-type schema is derived from the function's return annotation and
  surfaced via ``FunctionTool.return_schema`` and ``FunctionTool.describe``.
* Per-argument descriptions/examples (pydantic ``Field(description=...)`` or the
  ``arg_docs``/``examples`` kwargs) surface in ``parameters_schema``.
* ``scope`` / ``mutating`` / ``approval_required`` / ``cost_hint`` attach a
  :class:`~pirn_agents.tool_permissions.ToolPermissions` (S3, inert by default).
* An async-generator function becomes a *streaming* tool (S2).
* ``state`` injects a resource that persists across calls into a reserved
  ``state`` keyword parameter (S2).

The schema derivation itself lives in
:class:`~pirn_agents.tool_schema_compiler.ToolSchemaCompiler`; the concrete tool
type is :class:`~pirn_agents.function_tool.FunctionTool`. For tools that need
constructor dependencies (API keys, HTTP clients) subclass :class:`Tool` directly.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from inspect import isasyncgenfunction, iscoroutinefunction
from typing import Any

from pirn_agents.function_tool import FunctionTool
from pirn_agents.tool_permissions import ToolPermissions
from pirn_agents.tool_schema_compiler import ToolSchemaCompiler


def _build_tool(
    fn: Callable[..., Any],
    *,
    name: str | None,
    description: str | None,
    args_model: type | None,
    arg_docs: Mapping[str, str] | None,
    examples: Mapping[str, Any] | None,
    permissions: ToolPermissions,
    state: Any | None,
) -> FunctionTool:
    """Construct a :class:`FunctionTool` from ``fn`` and the decorator options."""
    if not callable(fn):
        raise TypeError(f"@tool requires a callable, got {type(fn).__name__}")
    compiler = ToolSchemaCompiler()
    if args_model is not None and not compiler.is_arg_model(args_model):
        raise TypeError("args_model must be a pydantic BaseModel subclass or a dataclass type")

    raw_doc = inspect.getdoc(fn) or ""
    resolved_description = description or raw_doc.split("\n\n")[0].strip() or fn.__name__
    is_stateful = state is not None

    if args_model is not None:
        parameters_schema: dict[str, Any] = compiler.model_json_schema(args_model)
        args_validator: Callable[[Mapping[str, Any]], Any] | None = compiler.model_validator(
            args_model
        )
    else:
        parameters_schema = compiler.schema_from_signature(
            fn,
            arg_docs=arg_docs,
            examples=examples,
            exclude=frozenset({"state"}) if is_stateful else frozenset(),
        )
        args_validator = None

    return FunctionTool(
        fn=fn,
        name=name or fn.__name__,
        description=resolved_description,
        parameters_schema=parameters_schema,
        is_async=iscoroutinefunction(fn) or isasyncgenfunction(fn),
        return_schema=compiler.return_schema(fn),
        permissions=permissions,
        args_validator=args_validator,
        is_streaming=isasyncgenfunction(fn),
        state=state,
        is_stateful=is_stateful,
    )


def tool(
    fn: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    args_model: type | None = None,
    arg_docs: Mapping[str, str] | None = None,
    examples: Mapping[str, Any] | None = None,
    scope: str | None = None,
    mutating: bool = False,
    approval_required: bool = False,
    cost_hint: float | None = None,
    state: Any | None = None,
) -> FunctionTool | Callable[[Callable[..., Any]], FunctionTool]:
    """Decorate a function as a pirn :class:`Tool`.

    Used bare (``@tool``) the function's name, docstring, and type-annotated
    parameters populate ``name``, ``description``, and ``parameters_schema``.
    Both sync and async functions are accepted; an async-generator function
    becomes a streaming tool.

    Used with arguments (``@tool(...)``) it additionally accepts:

    * ``args_model`` — a pydantic model or dataclass describing the arguments.
    * ``arg_docs`` / ``examples`` — per-argument descriptions/examples for the
      signature-derived schema.
    * ``scope`` / ``mutating`` / ``approval_required`` / ``cost_hint`` — the
      tool's :class:`~pirn_agents.tool_permissions.ToolPermissions`.
    * ``state`` — a resource injected into a reserved ``state`` keyword that
      persists across invocations.
    * ``name`` / ``description`` — explicit overrides.

    Example::

        @tool
        async def calculate(expression: str) -> str:
            \"\"\"Evaluate a mathematical expression and return the result.\"\"\"
            return str(eval(expression, {"__builtins__": {}}))
    """
    permissions = ToolPermissions(
        scope=scope,
        mutating=mutating,
        approval_required=approval_required,
        cost_hint=cost_hint,
    )

    def _decorate(target: Callable[..., Any]) -> FunctionTool:
        return _build_tool(
            target,
            name=name,
            description=description,
            args_model=args_model,
            arg_docs=arg_docs,
            examples=examples,
            permissions=permissions,
            state=state,
        )

    if fn is not None:
        # Bare `@tool` / direct `tool(fn)` call.
        return _decorate(fn)
    # Parametrised `@tool(...)` — return the decorator.
    return _decorate
