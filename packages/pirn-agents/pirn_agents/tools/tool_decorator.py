"""``ToolDecorator`` — the tool decorator: ``@KnotFactory.knot`` plus a declaration.

Basic usage stays a one-liner::

    from pirn_agents.tools.tool_decorator import ToolDecorator

    @ToolDecorator.decorate
    async def web_search(query: str, max_results: int = 5) -> str:
        \"\"\"Search the web and return a summary of the top results.\"\"\"
        ...  # your implementation

    # web_search is a FunctionTool (a ToolFactory): name="web_search",
    # description from the docstring, declaration parameters from the type
    # hints -- and web_search(query="x", _config=KnotConfig(id="c1")) is one call.

The decorated function becomes the ``process()`` of a generated
:class:`~pirn_agents.tools.tool.Tool` subclass, exactly as ``@KnotFactory.knot`` generates
a ``Knot`` subclass (ADR agents-speaks-core, WS1): the signature is the input
contract core validates with, a sync function runs via ``asyncio.to_thread``,
and the declaration is ``Knot.input_json_schema()`` rendered from the same
hints.  Both sync and async functions are accepted; an async-generator
function becomes a *streaming* tool whose call returns the drained chunks.

The decorator also has a **rich, parametrised form** alongside the bare
``@ToolDecorator.decorate`` above::

    from pydantic import BaseModel, Field

    class SearchArgs(BaseModel):
        query: str = Field(description="the search query")
        max_results: int = 5

    @ToolDecorator.decorate(args_model=SearchArgs, scope="web:read", cost_hint=1.0)
    async def web_search(args: SearchArgs) -> list[str]:
        \"\"\"Search the web.\"\"\"
        ...

* ``args_model`` — a pydantic model or dataclass whose JSON schema is the
  declared input schema (``Knot._input_schema_override``); incoming arguments
  are validated/coerced through it and the validated object is passed to the
  function.
* Return-type schema is derived from the function's return annotation and
  surfaced via ``FunctionTool.return_schema`` and ``FunctionTool.describe``.
* Per-argument descriptions/examples (pydantic ``Field(description=...)`` or the
  ``arg_docs``/``examples`` kwargs) surface in the declaration.
* ``scope`` / ``mutating`` / ``approval_required`` / ``cost_hint`` attach a
  :class:`~pirn_agents.tools.tool_permissions.ToolPermissions` (inert by default).
* ``state`` injects a resource that persists across calls into a reserved
  ``state`` keyword parameter; it is bound, never a knot input, so it is
  neither declared to the model nor validated.

For tools that need constructor-style dependencies (API keys, HTTP clients)
subclass :class:`Tool` directly and :meth:`Tool.bind` them.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
from collections.abc import Callable, Mapping
from dataclasses import is_dataclass
from inspect import isasyncgenfunction, iscoroutinefunction
from typing import Any, get_type_hints, overload

from pydantic import BaseModel, PydanticSchemaGenerationError, TypeAdapter

from pirn_agents.tools.function_tool import FunctionTool
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_permissions import ToolPermissions


class ToolDecorator:
    """Namespace for the ``@ToolDecorator.decorate`` decorator's implementation."""

    @staticmethod
    def build(
        fn: Callable[..., Any],
        *,
        name: str | None,
        description: str | None,
        args_model: type[object] | None,
        arg_docs: Mapping[str, str] | None,
        examples: Mapping[str, Any] | None,
        permissions: ToolPermissions,
        state: Any | None,
    ) -> FunctionTool:
        """Generate the ``Tool`` subclass for ``fn`` and wrap it as a :class:`FunctionTool`."""
        if not callable(fn):
            raise TypeError(f"@ToolDecorator.decorate requires a callable, got {type(fn).__name__}")
        if args_model is not None and not ToolDecorator._is_arg_model(args_model):
            raise TypeError("args_model must be a pydantic BaseModel subclass or a dataclass type")

        raw_doc = inspect.getdoc(fn) or ""
        resolved_name = name or fn.__name__
        resolved_description = description or raw_doc.split("\n\n")[0].strip() or fn.__name__
        is_stateful = state is not None
        is_stream = isasyncgenfunction(fn)
        is_async = iscoroutinefunction(fn) or is_stream

        validator = ToolDecorator._model_validator(args_model) if args_model is not None else None
        process = ToolDecorator._make_process(
            fn,
            is_async=is_async,
            is_stream=is_stream,
            state=state,
            is_stateful=is_stateful,
            validator=validator,
        )
        namespace: dict[str, Any] = {
            "process": process,
            "tool_name": resolved_name,
            "tool_description": resolved_description,
            "permissions": permissions,
            "streaming": is_stream,
            "__module__": fn.__module__,
            "__qualname__": fn.__qualname__,
            "__doc__": fn.__doc__,
        }
        if args_model is not None:
            namespace["_input_schema_override"] = ToolDecorator._model_json_schema(args_model)
        knot_class = type(fn.__name__, (Tool,), namespace)

        factory = FunctionTool(
            knot_class,
            fn=fn,
            return_schema=ToolDecorator._return_schema(fn),
            state=state,
            is_stateful=is_stateful,
            stream_fn=(
                (functools.partial(fn, state=state) if is_stateful else fn) if is_stream else None
            ),
        )
        if args_model is None and (arg_docs or examples):
            factory = ToolDecorator._with_argument_notes(factory, arg_docs, examples)
        return factory

    @staticmethod
    def _make_process(
        fn: Callable[..., Any],
        *,
        is_async: bool,
        is_stream: bool,
        state: Any | None,
        is_stateful: bool,
        validator: Callable[[Mapping[str, Any]], Any] | None,
    ) -> Callable[..., Any]:
        """Build the generated class's ``process()`` around ``fn``.

        The wrapper carries ``fn``'s signature and annotations (minus the
        injected ``state``) so core introspects the function's own contract;
        under ``args_model`` the declared schema override takes over instead.
        """

        # design-decision-override: closure over the wrapped function and its
        # bound state, used as the process() of the generated Tool subclass.
        async def process(self: Tool, **kwargs: Any) -> Any:
            positional: tuple[Any, ...] = ()
            keyword: dict[str, Any] = dict(kwargs)
            if validator is not None:
                positional = (validator(kwargs),)
                keyword = {}
            if is_stateful:
                keyword["state"] = state
            if is_stream:
                return [chunk async for chunk in fn(*positional, **keyword)]
            if is_async:
                return await fn(*positional, **keyword)
            return await asyncio.to_thread(fn, *positional, **keyword)

        functools.update_wrapper(process, fn)
        parameters = [
            parameter
            for parameter in inspect.signature(fn).parameters.values()
            if parameter.name not in ("self", "cls")
            and not (is_stateful and parameter.name == "state")
        ]
        # The trailing ``**_`` is the catch-all every knot's process() carries
        # (knot-design-rules.md, Rule 2); core checks for it on the wrapper
        # itself, so the published signature has to show it.
        parameters.append(inspect.Parameter("_", inspect.Parameter.VAR_KEYWORD))
        # ``inspect.signature`` reads ``__signature__`` from the function's
        # attribute dict, which is where attribute assignment would put it.
        process.__dict__["__signature__"] = inspect.Signature(parameters)
        # A streaming function's return hint types one chunk; the call's value
        # is the drained list, so the hint is dropped rather than misapplied.
        process.__annotations__ = {
            key: value
            for key, value in dict(getattr(fn, "__annotations__", {})).items()
            if not (is_stateful and key == "state") and not (is_stream and key == "return")
        }
        return process

    @staticmethod
    def _with_argument_notes(
        factory: FunctionTool,
        arg_docs: Mapping[str, str] | None,
        examples: Mapping[str, Any] | None,
    ) -> FunctionTool:
        """Return ``factory`` declaring ``arg_docs``/``examples`` on its parameters."""
        parameters = dict(factory.declaration().parameters)
        properties = {key: dict(value) for key, value in parameters.get("properties", {}).items()}
        for key, fragment in properties.items():
            if arg_docs and key in arg_docs:
                fragment["description"] = arg_docs[key]
            if examples and key in examples:
                fragment["examples"] = [examples[key]]
        parameters["properties"] = properties
        return factory.with_parameters(parameters)

    @staticmethod
    def _is_arg_model(spec: object) -> bool:
        """Return whether ``spec`` is a usable pydantic model or dataclass type."""
        if isinstance(spec, type) and issubclass(spec, BaseModel):
            return True
        return isinstance(spec, type) and is_dataclass(spec)

    @staticmethod
    def _model_json_schema(model: type[object]) -> dict[str, Any]:
        """Return the JSON schema for a pydantic model or dataclass ``model``."""
        if issubclass(model, BaseModel):
            schema = dict(model.model_json_schema())
        else:  # stdlib dataclass, validated via a pydantic TypeAdapter
            schema = dict(TypeAdapter(model).json_schema())
        schema.pop("title", None)
        return schema

    @staticmethod
    def _model_validator(model: type[object]) -> Callable[[Mapping[str, Any]], Any]:
        """Return a callable that validates/coerces a mapping into ``model``."""
        if issubclass(model, BaseModel):
            return functools.partial(ToolDecorator._validate_with_model, model)
        return functools.partial(ToolDecorator._validate_with_adapter, TypeAdapter(model))

    @staticmethod
    def _validate_with_model(model: type[BaseModel], data: Mapping[str, Any]) -> Any:
        """Validate ``data`` into a pydantic ``model`` instance."""
        return model.model_validate(dict(data))

    @staticmethod
    def _validate_with_adapter(adapter: TypeAdapter[Any], data: Mapping[str, Any]) -> Any:
        """Validate ``data`` into a dataclass via a pydantic ``adapter``."""
        return adapter.validate_python(dict(data))

    @staticmethod
    def _return_schema(fn: Callable[..., Any]) -> dict[str, Any] | None:
        """Derive a JSON Schema fragment from a function's return annotation."""
        try:
            hints = get_type_hints(fn)
        except Exception:
            return None
        annotation = hints.get("return", inspect.Parameter.empty)
        if annotation is inspect.Parameter.empty or annotation is None or annotation is type(None):
            return None
        if ToolDecorator._is_arg_model(annotation):
            return ToolDecorator._model_json_schema(annotation)
        try:
            fragment = dict(TypeAdapter(annotation).json_schema())
        except PydanticSchemaGenerationError:
            return None
        fragment.pop("title", None)
        return fragment or None

    @overload
    @staticmethod
    def decorate(fn: Callable[..., Any], /) -> FunctionTool: ...

    @overload
    @staticmethod
    def decorate(
        fn: None = None,
        /,
        *,
        name: str | None = None,
        description: str | None = None,
        args_model: type[object] | None = None,
        arg_docs: Mapping[str, str] | None = None,
        examples: Mapping[str, Any] | None = None,
        scope: str | None = None,
        mutating: bool = False,
        approval_required: bool = False,
        cost_hint: float | None = None,
        state: Any | None = None,
    ) -> Callable[[Callable[..., Any]], FunctionTool]: ...

    @staticmethod
    def decorate(
        fn: Callable[..., Any] | None = None,
        /,
        *,
        name: str | None = None,
        description: str | None = None,
        args_model: type[object] | None = None,
        arg_docs: Mapping[str, str] | None = None,
        examples: Mapping[str, Any] | None = None,
        scope: str | None = None,
        mutating: bool = False,
        approval_required: bool = False,
        cost_hint: float | None = None,
        state: Any | None = None,
    ) -> FunctionTool | Callable[[Callable[..., Any]], FunctionTool]:
        """Decorate a function as a pirn tool capability.

        Used bare (``@ToolDecorator.decorate``) the function's name, docstring, and
        type-annotated parameters populate the declaration. Both sync and
        async functions are accepted; an async-generator function becomes a
        streaming tool.

        Used with arguments (``@ToolDecorator.decorate(...)``) it additionally accepts:

        * ``args_model`` — a pydantic model or dataclass describing the arguments.
        * ``arg_docs`` / ``examples`` — per-argument descriptions/examples for the
          signature-derived schema.
        * ``scope`` / ``mutating`` / ``approval_required`` / ``cost_hint`` — the
          tool's :class:`~pirn_agents.tools.tool_permissions.ToolPermissions`.
        * ``state`` — a resource injected into a reserved ``state`` keyword that
          persists across invocations.
        * ``name`` / ``description`` — explicit overrides.
        """
        permissions = ToolPermissions(
            scope=scope,
            mutating=mutating,
            approval_required=approval_required,
            cost_hint=cost_hint,
        )
        decorate = functools.partial(
            ToolDecorator.build,
            name=name,
            description=description,
            args_model=args_model,
            arg_docs=arg_docs,
            examples=examples,
            permissions=permissions,
            state=state,
        )
        if fn is not None:
            # Bare `@ToolDecorator.decorate` / direct `ToolDecorator.decorate(fn)` call.
            return decorate(fn)
        # Parametrised `@ToolDecorator.decorate(...)` — return the decorator.
        return decorate
