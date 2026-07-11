"""``@tool`` decorator — convert a plain function into a rich :class:`Tool`.

Basic usage stays a one-liner::

    from pirn_agents.tool_decorator import tool

    @tool
    async def web_search(query: str, max_results: int = 5) -> str:
        \"\"\"Search the web and return a summary of the top results.\"\"\"
        ...  # your implementation

    # web_search is now a Tool: name="web_search", description from the
    # docstring, parameters_schema derived from the type hints.

Sync functions are accepted too — :meth:`FunctionTool.invoke` wraps them in
``asyncio.to_thread`` automatically.

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
  surfaced via :attr:`FunctionTool.return_schema` and :meth:`FunctionTool.describe`.
* Per-argument descriptions/examples (pydantic ``Field(description=...)`` or the
  ``arg_docs``/``examples`` kwargs) surface in ``parameters_schema``.
* ``scope`` / ``mutating`` / ``approval_required`` / ``cost_hint`` attach a
  :class:`~pirn_agents.tool_permissions.ToolPermissions` (S3, inert by default).
* An async-generator function becomes a *streaming* tool (S2).
* ``state`` injects a resource that persists across calls into a reserved
  ``state`` keyword parameter (S2).

For tools that need constructor dependencies (API keys, HTTP clients) subclass
:class:`Tool` directly.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import is_dataclass
from inspect import isasyncgenfunction, iscoroutinefunction
from typing import Any, Union, get_type_hints

from pydantic import BaseModel, TypeAdapter

from pirn_agents.tool import Tool
from pirn_agents.tool_permissions import ToolPermissions

# ---------------------------------------------------------------------------
# JSON Schema type mapping
# ---------------------------------------------------------------------------

_py_to_json_type: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    bytes: "string",
    list: "array",
    dict: "object",
}


def _annotation_to_schema(annotation: Any) -> dict[str, Any]:
    """Best-effort conversion of a Python type hint to a JSON Schema fragment."""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {}

    origin = getattr(annotation, "__origin__", None)
    args: tuple[Any, ...] = getattr(annotation, "__args__", ()) or ()

    # Optional[T] / Union[T, None]
    if origin is Union:
        non_none = [a for a in args if a is not type(None)]
        nullable = len(non_none) < len(args)
        if len(non_none) == 1:
            inner = _annotation_to_schema(non_none[0])
            if nullable:
                t = inner.get("type")
                if isinstance(t, str):
                    inner = {**inner, "type": [t, "null"]}
            return inner
        return {}

    # Python 3.10+ `X | Y` syntax surfaces as types.UnionType
    try:
        import types as _types

        if isinstance(annotation, _types.UnionType):
            parts = list(args) if args else []
            # Fall back to __args__ populated by __class_getitem__
            if not parts:
                parts = list(getattr(annotation, "__args__", []))
            non_none = [a for a in parts if a is not type(None)]
            nullable = len(non_none) < len(parts)
            if len(non_none) == 1:
                inner = _annotation_to_schema(non_none[0])
                if nullable:
                    t = inner.get("type")
                    if isinstance(t, str):
                        inner = {**inner, "type": [t, "null"]}
                return inner
            return {}
    except AttributeError:
        pass

    # list[T] / List[T]
    if origin is list:
        schema: dict[str, Any] = {"type": "array"}
        if args:
            schema["items"] = _annotation_to_schema(args[0])
        return schema

    # dict[K, V] / Dict[K, V]
    if origin is dict:
        return {"type": "object"}

    json_type = _py_to_json_type.get(annotation)
    if json_type:
        return {"type": json_type}

    # Unknown annotation — leave the field schema-less so tools still work.
    return {}


def _is_arg_model(spec: Any) -> bool:
    """Return whether ``spec`` is a usable pydantic model or dataclass type."""
    if isinstance(spec, type) and issubclass(spec, BaseModel):
        return True
    return isinstance(spec, type) and is_dataclass(spec)


def _model_json_schema(model: type) -> dict[str, Any]:
    """Return the JSON schema for a pydantic model or dataclass ``model``."""
    if issubclass(model, BaseModel):
        schema = dict(model.model_json_schema())
    else:  # stdlib dataclass, validated via a pydantic TypeAdapter
        schema = dict(TypeAdapter(model).json_schema())
    schema.pop("title", None)
    return schema


def _model_validator(model: type) -> Callable[[Mapping[str, Any]], Any]:
    """Return a callable that validates/coerces a mapping into ``model``."""
    if issubclass(model, BaseModel):

        def _validate_model(data: Mapping[str, Any]) -> Any:
            return model.model_validate(dict(data))

        return _validate_model

    adapter = TypeAdapter(model)

    def _validate_dataclass(data: Mapping[str, Any]) -> Any:
        return adapter.validate_python(dict(data))

    return _validate_dataclass


def _schema_from_signature(
    fn: Callable[..., Any],
    *,
    arg_docs: Mapping[str, str] | None,
    examples: Mapping[str, Any] | None,
    exclude: frozenset[str],
) -> dict[str, Any]:
    """Derive a JSON Schema ``parameters`` object from a function's signature.

    ``arg_docs`` and ``examples`` decorate the per-argument fragments with
    ``description``/``examples`` keys; ``exclude`` drops reserved parameters
    (e.g. an injected ``state``) from the surfaced schema.
    """
    sig = inspect.signature(fn)
    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = {}

    properties: dict[str, dict[str, Any]] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        if name in ("self", "cls") or name in exclude:
            continue
        annotation = hints.get(name, inspect.Parameter.empty)
        prop = _annotation_to_schema(annotation)
        if arg_docs and name in arg_docs:
            prop["description"] = arg_docs[name]
        if examples and name in examples:
            prop["examples"] = [examples[name]]
        properties[name] = prop
        if param.default is inspect.Parameter.empty:
            required.append(name)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _return_schema(fn: Callable[..., Any]) -> dict[str, Any] | None:
    """Derive a JSON Schema fragment from a function's return annotation."""
    try:
        hints = get_type_hints(fn)
    except Exception:
        return None
    annotation = hints.get("return", inspect.Parameter.empty)
    if annotation is inspect.Parameter.empty or annotation is None or annotation is type(None):
        return None
    if _is_arg_model(annotation):
        return _model_json_schema(annotation)
    fragment = _annotation_to_schema(annotation)
    return fragment or None


# ---------------------------------------------------------------------------
# FunctionTool — the concrete Tool produced by @tool
# ---------------------------------------------------------------------------


class FunctionTool(Tool):
    """A :class:`Tool` backed by a plain Python function.

    Produced by the :func:`tool` decorator. Do not instantiate directly.
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        *,
        name: str,
        description: str,
        parameters_schema: Mapping[str, Any],
        is_async: bool,
        return_schema: Mapping[str, Any] | None = None,
        permissions: ToolPermissions | None = None,
        args_validator: Callable[[Mapping[str, Any]], Any] | None = None,
        is_streaming: bool = False,
        state: Any | None = None,
        is_stateful: bool = False,
    ) -> None:
        self._fn = fn
        self._name = name
        self._description = description
        self._parameters_schema = dict(parameters_schema)
        self._is_async = is_async
        self._return_schema = dict(return_schema) if return_schema is not None else None
        self._permissions = permissions if permissions is not None else ToolPermissions()
        self._args_validator = args_validator
        self._is_streaming = is_streaming
        self._state = state
        self._is_stateful = is_stateful

    @property
    def name(self) -> str:
        """Stable identifier derived from the wrapped function's ``__name__``."""
        return self._name

    @property
    def description(self) -> str:
        """First docstring paragraph of the wrapped function, or the function name."""
        return self._description

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """JSON Schema object describing the tool's arguments."""
        return self._parameters_schema

    @property
    def return_schema(self) -> Mapping[str, Any] | None:
        """JSON Schema fragment for the return value, or ``None`` if untyped."""
        return self._return_schema

    @property
    def permissions(self) -> ToolPermissions:
        """Permission / scope metadata attached to this tool."""
        return self._permissions

    @property
    def streaming(self) -> bool:
        """Return whether this tool yields incremental output via :meth:`stream`."""
        return self._is_streaming

    @property
    def stateful(self) -> bool:
        """Return whether this tool carries injected state across calls."""
        return self._is_stateful

    @property
    def state(self) -> Any | None:
        """Return the injected state/resource object, or ``None``."""
        return self._state

    def _prepare_call(self, arguments: Mapping[str, Any]) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """Build the positional/keyword arguments for the wrapped function.

        When an ``args_model`` is configured the mapping is validated/coerced
        and the validated object is passed positionally; otherwise the mapping
        is spread as keyword arguments. An injected ``state`` is appended as a
        reserved ``state`` keyword.
        """
        if self._args_validator is not None:
            positional: tuple[Any, ...] = (self._args_validator(arguments),)
            keyword: dict[str, Any] = {}
        else:
            positional = ()
            keyword = dict(arguments)
        if self._is_stateful:
            keyword["state"] = self._state
        return positional, keyword

    def stream(self, arguments: Mapping[str, Any]) -> AsyncIterator[Any]:
        """Return the async iterator of partial results for ``arguments``.

        Raises
        ------
        TypeError
            If this tool is not a streaming (async-generator) tool.
        """
        if not self._is_streaming:
            raise TypeError(f"tool {self._name!r} is not a streaming tool")
        positional, keyword = self._prepare_call(arguments)
        return self._fn(*positional, **keyword)

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        """Call the wrapped function with ``arguments``.

        Async functions are awaited directly; sync functions run in a thread
        via ``asyncio.to_thread`` so the event loop is never blocked. Streaming
        tools are drained and their chunks returned as a list, so callers that
        expect a single value keep working.
        """
        if self._is_streaming:
            return [chunk async for chunk in self.stream(arguments)]
        positional, keyword = self._prepare_call(arguments)
        if self._is_async:
            return await self._fn(*positional, **keyword)
        return await asyncio.to_thread(self._fn, *positional, **keyword)

    def describe(self) -> dict[str, Any]:
        """Return the full tool descriptor: name, description, params, returns, perms.

        ``returns`` is present only when the return type is annotated;
        ``permissions`` only when non-default. The neutral
        ``{name, description, parameters}`` core matches
        :meth:`pirn_agents.toolset.Toolset.schema` entries.
        """
        descriptor: dict[str, Any] = {
            "name": self._name,
            "description": self._description,
            "parameters": dict(self._parameters_schema),
        }
        if self._return_schema is not None:
            descriptor["returns"] = dict(self._return_schema)
        fragment = self._permissions.as_schema_fragment()
        if fragment:
            descriptor["permissions"] = fragment
        return descriptor

    def __repr__(self) -> str:
        return f"<FunctionTool name={self._name!r}>"


# ---------------------------------------------------------------------------
# @tool decorator
# ---------------------------------------------------------------------------


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
    if args_model is not None and not _is_arg_model(args_model):
        raise TypeError("args_model must be a pydantic BaseModel subclass or a dataclass type")

    raw_doc = inspect.getdoc(fn) or ""
    resolved_description = description or raw_doc.split("\n\n")[0].strip() or fn.__name__
    is_stateful = state is not None

    if args_model is not None:
        parameters_schema: dict[str, Any] = _model_json_schema(args_model)
        args_validator: Callable[[Mapping[str, Any]], Any] | None = _model_validator(args_model)
    else:
        parameters_schema = _schema_from_signature(
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
        return_schema=_return_schema(fn),
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
