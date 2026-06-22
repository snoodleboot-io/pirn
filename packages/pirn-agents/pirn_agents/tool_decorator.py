"""``@tool`` decorator — convert a plain function into a :class:`Tool`.

Usage::

    from pirn_agents.tool_decorator import tool

    @tool
    async def web_search(query: str, max_results: int = 5) -> str:
        \"\"\"Search the web and return a summary of the top results.\"\"\"
        ...  # your implementation

    # web_search is now a Tool instance; name="web_search", description from docstring,
    # parameters_schema derived from type hints.

    react = ReActLoop(messages=msgs, llm=llm, tools=[web_search], ...)

Sync functions are also accepted — ``invoke`` wraps them in
``asyncio.to_thread`` automatically.

The decorator is intentionally minimal.  For tools that need
constructor dependencies (API keys, HTTP clients, etc.) use the
:class:`Tool` class directly.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Mapping
from inspect import iscoroutinefunction
from typing import Any, Union, get_type_hints

from pirn_agents.tool import Tool

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


def _build_parameters_schema(fn: Callable[..., Any]) -> Mapping[str, Any]:
    """Derive a JSON Schema ``parameters`` object from a function's signature."""
    sig = inspect.signature(fn)
    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = {}

    properties: dict[str, dict[str, Any]] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        annotation = hints.get(name, inspect.Parameter.empty)
        prop = _annotation_to_schema(annotation)
        properties[name] = prop
        if param.default is inspect.Parameter.empty:
            required.append(name)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


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
    ) -> None:
        self._fn = fn
        self._name = name
        self._description = description
        self._parameters_schema = dict(parameters_schema)
        self._is_async = is_async

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
        """JSON Schema object derived from the wrapped function's type annotations."""
        return self._parameters_schema

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        """Call the wrapped function with ``arguments`` as keyword arguments.

        Async functions are awaited directly; sync functions run in a thread
        via ``asyncio.to_thread`` so the event loop is never blocked.
        """
        kwargs = dict(arguments)
        if self._is_async:
            return await self._fn(**kwargs)
        return await asyncio.to_thread(self._fn, **kwargs)

    def __repr__(self) -> str:
        return f"<FunctionTool name={self._name!r}>"


# ---------------------------------------------------------------------------
# @tool decorator
# ---------------------------------------------------------------------------


def tool(fn: Callable[..., Any]) -> FunctionTool:
    """Decorate a function as a pirn :class:`Tool`.

    The function's name, docstring, and type-annotated parameters are
    used to populate the ``name``, ``description``, and
    ``parameters_schema`` properties respectively. Both sync and async
    functions are accepted.

    Example::

        @tool
        async def calculate(expression: str) -> str:
            \"\"\"Evaluate a mathematical expression and return the result.\"\"\"
            return str(eval(expression, {"__builtins__": {}}))

        @tool
        def lookup_policy(topic: str) -> str:
            \"\"\"Look up an internal policy document by topic keyword.\"\"\"
            return POLICIES.get(topic, "No policy found.")

    The decorated name can be passed directly anywhere a :class:`Tool`
    is accepted::

        react = ReActLoop(messages=msgs, llm=llm, tools=[calculate, lookup_policy], ...)
    """
    if not callable(fn):
        raise TypeError(f"@tool requires a callable, got {type(fn).__name__}")

    raw_doc = inspect.getdoc(fn) or ""
    description = raw_doc.split("\n\n")[0].strip() or fn.__name__

    return FunctionTool(
        fn=fn,
        name=fn.__name__,
        description=description,
        parameters_schema=_build_parameters_schema(fn),
        is_async=iscoroutinefunction(fn),
    )
