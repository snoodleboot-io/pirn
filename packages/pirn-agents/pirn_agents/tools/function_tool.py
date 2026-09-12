"""``FunctionTool`` — the concrete :class:`Tool` produced by the ``@tool`` decorator.

Wraps a plain Python function (sync, async, or async-generator) with a
pre-compiled name / description / parameters schema and optional argument
validator, streaming flag, and injected state. It is constructed by the
:func:`~pirn_agents.tools.tool_decorator.tool` decorator — not instantiated directly.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator, Callable, Mapping
from typing import Any

from pirn_agents.tools.definition_reference import DefinitionReference
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_permissions import ToolPermissions
from pirn_agents.tools.tool_schema_compiler import ToolSchemaCompiler


class FunctionTool(Tool):
    """A :class:`Tool` backed by a plain Python function.

    Produced by the :func:`~pirn_agents.tools.tool_decorator.tool` decorator. Do not
    instantiate directly.
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
        args_model: type | None = None,
    ) -> None:
        self._fn = fn
        self._args_model = args_model
        self._name = name
        self._description = description
        self._parameters_schema = dict(parameters_schema)
        self._is_async = is_async
        self._return_schema = dict(return_schema) if return_schema is not None else None
        self._permissions = permissions if permissions is not None else ToolPermissions()
        # A validator derived here from ``args_model`` is fully described by the
        # model; one passed in is an arbitrary callable with no content form.
        self._has_custom_validator = args_validator is not None
        if args_validator is None and args_model is not None:
            args_validator = ToolSchemaCompiler().model_validator(args_model)
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

    def content_identity(self) -> Mapping[str, Any] | None:
        """Opt in to content identity only when every behavioural input has a stable form.

        The tool stays identity-keyed (``None``) unless all of these hold:

        * ``fn`` is a plain function with a unique, process-independent name
          (:class:`~pirn_agents.tools.definition_reference.DefinitionReference`):
          not a lambda, a ``<locals>`` closure, a bound method, a partial, a
          callable object, a shadowed definition, or a ``__main__`` function
          without a script file. A ``__main__`` function is named by the resolved
          absolute script path, so a different script defining the same name
          refuses;
        * ``fn`` has no closure and no ``__wrapped__``. A ``functools.wraps``
          decorator copies the wrapped qualname, so without this rule a wrapper
          closing over config (``@scoped(os.environ["TENANT"])``) would hash
          equal for every value of that config;
        * every default argument value is plain data (``None``, ``bool``,
          ``int``, ``float``, ``str``, and lists/tuples/str-keyed dicts of them),
          and the defaults are hashed — the schema does not carry them;
        * no custom ``args_validator`` was passed. A validator the tool derives
          from ``args_model`` is fine, and the model must itself have a unique name;
        * any injected ``state`` defines ``__pirn_canonical__``, so its author has
          declared what identifies it. State without one (a connection, a
          client, a mutable dict) keeps the tool identity-keyed.

        Accepted limits (PIR-840, Q7): the function body is not digested, and
        module globals the body reads are not hashed. An edited body, or a
        changed global, at an unchanged module path or script path still
        matches, the same as a knot's ``process`` in core replay.
        """
        if self._has_custom_validator or not inspect.isfunction(self._fn):
            return None
        if self._fn.__closure__ or "__wrapped__" in vars(self._fn):
            return None
        fn_reference = DefinitionReference.of(self._fn, unwrap_binding=self._unwrap_binding)
        if fn_reference is None:
            return None
        defaults = self._defaults_identity(self._fn)
        if defaults is None:
            return None
        model_reference: str | None = None
        if self._args_model is not None:
            model_reference = DefinitionReference.of(self._args_model)
            if model_reference is None:
                return None
        if self._state is not None and not hasattr(type(self._state), "__pirn_canonical__"):
            return None
        return {
            "fn": fn_reference,
            "defaults": defaults,
            "args_model": model_reference,
            "return_schema": self._return_schema,
            "permissions": self._permissions,
            "is_async": self._is_async,
            "streaming": self._is_streaming,
            "stateful": self._is_stateful,
            "state": self._state,
        }

    @staticmethod
    def _unwrap_binding(bound: object) -> object:
        """Map a module binding to the function it stands for (``@tool`` rebinds names)."""
        return bound._fn if isinstance(bound, FunctionTool) else bound

    @staticmethod
    def _defaults_identity(fn: Callable[..., Any]) -> dict[str, Any] | None:
        """Return ``fn``'s default values as plain data, or ``None`` if any has no content form."""
        positional = list(fn.__defaults__) if fn.__defaults__ is not None else None
        keyword = dict(fn.__kwdefaults__) if fn.__kwdefaults__ is not None else None
        if not FunctionTool._is_plain_data([positional, keyword]):
            return None
        return {"positional": positional, "keyword": keyword}

    @staticmethod
    def _is_plain_data(value: object) -> bool:
        """Return whether ``value`` is JSON-like data whose hash fully describes it."""
        if value is None or isinstance(value, (bool, int, float, str)):
            return True
        if isinstance(value, (list, tuple)):
            return all(FunctionTool._is_plain_data(item) for item in value)
        if isinstance(value, dict):
            return all(
                isinstance(key, str) and FunctionTool._is_plain_data(item)
                for key, item in value.items()
            )
        return False

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
        ``permissions`` only when non-default. The neutral core is this tool's
        :class:`~pirn_agents.tools.tool_declaration.ToolDeclaration`, so it is
        the same triple — same keys, same order — that
        :meth:`pirn_agents.tools.toolset.Toolset.schema` emits.
        """
        descriptor: dict[str, Any] = self.declaration().to_payload()
        if self._return_schema is not None:
            descriptor["returns"] = dict(self._return_schema)
        fragment = self._permissions.as_schema_fragment()
        if fragment:
            descriptor["permissions"] = fragment
        return descriptor

    def __repr__(self) -> str:
        return f"<FunctionTool name={self._name!r}>"
