"""``ToolFactory`` — a tool capability as a value: a knot class plus what is bound to it.

The ADR "agents speaks core" (WS1) makes the *class* the capability and an
*instance* one call.  A capability still has to travel as a value — in a
:class:`~pirn_agents.tools.toolset.Toolset`, as a knot input named ``tools``,
in a registry — and a bare class cannot carry the dependencies a call never
supplies (a filesystem root, a database connector).  ``ToolFactory`` is that
value: a :class:`~pirn.core.knot_factory.KnotFactory` (``@ToolDecorator.decorate`` is ``@KnotFactory.knot``
plus a declaration) over any ``Knot`` class, with the inputs :meth:`bind`
pre-fills, and the model-facing envelope read off the class.

Everything a caller used to read off a ``Tool`` instance is read here instead:
``name``, ``description``, :meth:`declaration`, ``permissions``,
:meth:`requires_approval`, ``streaming``/:meth:`stream`.  Executing a
:class:`~pirn_agents.tools.tool_call.ToolCall` is :meth:`for_call` — a knot
with ``KnotConfig(id=call_id)`` and the call's arguments as inputs, which the
engine then validates, schedules, retries and times out like any other.

Algorithm (``for_call``):
    1. Alias — a lone ReAct-style ``input``/``task``/``query`` argument the
       declaration does not name is moved onto the declaration's primary
       parameter (first required, else first declared), so a single-string
       tool works under the text ReAct loop as well as schema-based calling.
    2. Validate — required, unknown and mistyped arguments are reported
       together as :class:`~pirn_agents.exceptions.tool_argument_validation_error.ToolArgumentValidationError`
       (``{name: reason}``), using the declaration's schema through core's
       ``JsonSchemaTypeBuilder`` adapters — the same machinery
       ``validate_io`` uses.
    3. Construct — ``knot_class(**bound, **arguments, _config=KnotConfig(id=knot_id_for(call_id),
       timeout=..., retry=..., concurrency_group=...))``.  A ``call_id`` that
       is not a valid knot id is hashed into one.

Any ``Knot`` class is a capability.  A ``SubTapestry`` agent, a ``@KnotFactory.knot``
function, a plain knot — :meth:`of` accepts the class, a ``KnotFactory``, or
an already-configured instance (whose literal inputs become the binding).
Only :class:`~pirn_agents.tools.tool.Tool` subclasses add the envelope
attributes; every other class gets a name from its class name and a
description from its docstring.

Deprecated shape (one cycle): :meth:`of` also wraps a pre-ADR, ``invoke``-shaped
``Tool`` instance in a schema-declared knot whose single input is the argument
mapping, so it keeps working as a capability without being a knot.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import re
from collections.abc import AsyncIterator, Callable, Collection, Mapping
from inspect import iscoroutinefunction
from typing import Any, ClassVar

from pirn.core.json_schema_type_builder import JsonSchemaTypeBuilder
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.core.parameter import Parameter
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.core.result import Result
from pirn.nodes.gate.gate import Gate
from pydantic import (
    GetCoreSchemaHandler,
    PydanticSchemaGenerationError,
    TypeAdapter,
    ValidationError,
)
from pydantic_core import CoreSchema, core_schema

from pirn_agents.exceptions.tool_argument_validation_error import (
    ToolArgumentValidationError,
)
from pirn_agents.tools.definition_reference import DefinitionReference
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_declaration import ToolDeclaration
from pirn_agents.tools.tool_permissions import ToolPermissions


class ToolFactory(KnotFactory, PirnOpaqueValue):
    """A tool capability: a ``Knot`` class, its bound inputs, and its declaration."""

    #: ReAct-style argument names aliased onto a declaration's primary parameter.
    _aliases: ClassVar[tuple[str, ...]] = ("input", "task", "query")
    _identifier_re: ClassVar[re.Pattern[str]] = re.compile(r"\W")
    _snake_case_re: ClassVar[re.Pattern[str]] = re.compile(r"(?<!^)(?=[A-Z])")

    def __init__(
        self,
        knot_class: type[Knot],
        *,
        bound: Mapping[str, Any] | None = None,
        fn: Callable[..., Any] | None = None,
        name: str | None = None,
        description: str | None = None,
        parameters: Mapping[str, Any] | None = None,
        hidden: Collection[str] = (),
    ) -> None:
        """Wrap *knot_class* as a capability.

        Args:
            knot_class: Any ``Knot`` subclass; one instance is one call.
            bound: Inputs every call carries and the declaration hides.
            fn: The function the class was generated from, for introspection
                (``KnotFactory.fn``); defaults to the class itself.
            name: Override for the declared name.
            description: Override for the declared description.
            parameters: Override for the declared JSON ``parameters`` schema;
                derived from ``knot_class.input_json_schema()`` when omitted.
            hidden: Extra input names to hide from the declaration without
                binding them (dependencies an agent receives some other way).

        Raises:
            TypeError: If *knot_class* is not a ``Knot`` subclass.
        """
        if not (isinstance(knot_class, type) and issubclass(knot_class, Knot)):
            raise TypeError(f"ToolFactory: knot_class must be a Knot subclass, got {knot_class!r}")
        super().__init__(fn=fn if fn is not None else knot_class, knot_class=knot_class)
        self._bound: dict[str, Any] = dict(bound) if bound else {}
        self._name = name
        self._description = description
        self._parameters: dict[str, Any] | None = (
            dict(parameters) if parameters is not None else None
        )
        self._hidden: frozenset[str] = frozenset(hidden)
        self._defaults: dict[str, Any] = {}
        self._packs_arguments = False

    # ------------------------------------------------------------ building

    @classmethod
    def of(cls, candidate: Any) -> ToolFactory:
        """Return *candidate* as a :class:`ToolFactory`.

        Accepts a factory (returned as is), a ``KnotFactory`` (``@KnotFactory.knot``,
        ``@ToolDecorator.decorate``), a ``Knot`` class, or a configured ``Knot`` instance (its
        literal inputs and defaulted parameters become the binding).

        Raises:
            TypeError: For anything else, or an instance whose inputs are
                wired to upstream knots and so cannot be re-bound per call.
        """
        if isinstance(candidate, ToolFactory):
            return candidate
        if isinstance(candidate, KnotFactory):
            return cls(candidate.knot_class, fn=candidate.fn)
        if isinstance(candidate, type) and issubclass(candidate, Knot):
            return cls(candidate)
        if isinstance(candidate, Knot):
            return cls.from_knot(candidate)
        raise TypeError(
            f"ToolFactory.of: expected a Knot class, a KnotFactory, a configured Knot or a "
            f"ToolFactory, got {type(candidate).__name__}"
        )

    @classmethod
    def from_knot(cls, instance: Knot) -> ToolFactory:
        """Use a configured knot as the template for per-call instances.

        Its ``config_values`` and the defaults of its auto-coerced
        ``Parameter`` parents are bound; a parent wired to a real upstream
        knot cannot be, because a call has no run to resolve it in.
        """
        bound: dict[str, Any] = dict(instance.config_values)
        for input_name, parent in instance.parents.items():
            if isinstance(parent, Parameter) and parent.has_default:
                bound[input_name] = parent.default
                continue
            raise TypeError(
                f"ToolFactory.from_knot: {type(instance).__name__}({instance.knot_id!r}) input "
                f"{input_name!r} is wired to knot {parent.knot_id!r}; a capability must be "
                "constructible per call, so bind it to a value instead"
            )
        return cls(type(instance), bound=bound)

    @classmethod
    def schema_declared_class(
        cls,
        class_name: str,
        input_schema: Mapping[str, Any],
        process: Callable[..., Any],
        *,
        description: str | None = None,
        tool_name: str | None = None,
    ) -> type[Tool]:
        """Generate a ``Tool`` subclass whose inputs are declared by a JSON schema.

        The ``Tool``-based counterpart of ``KnotFactory.from_schema``: for a
        capability with no Python signature to introspect — an MCP-declared
        tool, an OpenAPI operation — the schema is the input contract, and
        each property becomes the ``TypeAdapter`` ``validate_io`` applies.

        Args:
            class_name: The generated class's name (non-identifier characters
                are replaced).
            input_schema: A JSON object schema with a ``properties`` mapping.
            process: Async or sync callable receiving the validated inputs by
                keyword; a sync callable runs via ``asyncio.to_thread``.
            description: The declared description (and class docstring).
            tool_name: The declared name; defaults to the class name.

        Raises:
            TypeError: If *input_schema* is not an object schema, names a
                framework-reserved property, or requires an undeclared one.
        """
        schema = JsonSchemaTypeBuilder.validate_input_schema(
            input_schema, reserved=Knot._reserved_kwargs
        )
        if iscoroutinefunction(process):
            # design-decision-override: closure over ``process``, the body of
            # the generated class's process().
            async def process_method(self: Tool, **kwargs: Any) -> Any:
                return await process(**kwargs)

        else:
            # design-decision-override: closure over ``process``, the body of
            # the generated class's process(); a sync callable leaves the loop.
            async def process_method(self: Tool, **kwargs: Any) -> Any:
                return await asyncio.to_thread(process, **kwargs)

        safe_name = cls._identifier_re.sub("_", class_name) or "Tool"
        if safe_name[0].isdigit():
            safe_name = f"_{safe_name}"
        namespace: dict[str, Any] = {
            "process": process_method,
            "_input_schema_override": schema,
            "tool_name": tool_name,
            "tool_description": description,
            "__module__": getattr(process, "__module__", __name__),
            "__qualname__": safe_name,
            "__doc__": description,
        }
        return type(safe_name, (Tool,), namespace)

    def bind(self, **config: Any) -> ToolFactory:
        """Return a copy of this factory with *config* bound on top of the existing binding.

        A bound input is fixed for every call and hidden from the declaration:
        a dependency (a store, a connector, a root directory) or a policy the
        model must not be able to change.  Each value is validated eagerly
        against the input's declared type, so a wrong dependency fails here
        rather than on the first call.

        Raises:
            TypeError: If a value does not satisfy its input's type, or names
                an input the knot class does not declare.
        """
        self._validate_bound(config)
        clone = copy.copy(self)
        clone._bound = {**self._bound, **config}
        return clone

    def named(self, name: str, *, description: str | None = None) -> ToolFactory:
        """Return a copy declared under *name* (and *description*, when given).

        The knot class is unchanged; only the model-facing envelope differs,
        so two bindings of one class can be offered as distinct tools.
        """
        if not isinstance(name, str) or not name:
            raise TypeError(f"{self.name}: a declared name must be a non-empty str, got {name!r}")
        clone = copy.copy(self)
        clone._name = name
        if description is not None:
            clone._description = description
        return clone

    def defaults(self, **values: Any) -> ToolFactory:
        """Return a copy whose calls default to *values* unless the call supplies them.

        Unlike :meth:`bind`, a default stays declared to the model — the
        declaration shows it as the property's ``default`` — and a call may
        override it.  Use it for tunables (a result count) rather than
        dependencies or policy.

        Raises:
            TypeError: If a value does not satisfy its input's type, or names
                an input the knot class does not declare.
        """
        self._validate_bound(values)
        clone = copy.copy(self)
        clone._defaults = {**self._defaults, **values}
        return clone

    def _validate_bound(self, values: Mapping[str, Any]) -> None:
        """Check *values* against the knot class's declared input types."""
        if self._packs_arguments:
            return
        annotations = self._input_annotations()
        for name, value in values.items():
            if name not in annotations:
                raise TypeError(
                    f"{self.name}: cannot bind {name!r}; declared inputs are "
                    f"{sorted(annotations)!r}"
                )
            annotation = annotations[name]
            if annotation is Any:
                continue
            try:
                adapter = TypeAdapter(annotation)
            except PydanticSchemaGenerationError:
                continue
            try:
                adapter.validate_python(value)
            except ValidationError as exc:
                raise TypeError(f"{self.name}: bound value for {name!r} is invalid: {exc}") from exc

    def _input_annotations(self) -> dict[str, Any]:
        """Name -> validation annotation for each declared ``process()`` input."""
        knot_class = self.knot_class
        schema = knot_class._input_schema_override
        if schema is not None:
            return {
                name: JsonSchemaTypeBuilder.python_type(fragment, root=schema)
                for name, fragment in schema.get("properties", {}).items()
            }
        signature = inspect.signature(knot_class.process)
        return knot_class._input_annotations(signature, knot_class._process_hints(signature))

    # ------------------------------------------------------------ envelope

    @property
    def bound(self) -> Mapping[str, Any]:
        """The inputs every call carries and the declaration hides."""
        return dict(self._bound)

    @property
    def name(self) -> str:
        """The name the model addresses the tool by."""
        if self._name is not None:
            return self._name
        if issubclass(self.knot_class, Tool):
            return self.knot_class.declared_name()
        return self._snake_case_re.sub("_", self.knot_class.__name__).lower()

    @property
    def description(self) -> str:
        """The description shown to the model."""
        if self._description is not None:
            return self._description
        if issubclass(self.knot_class, Tool):
            return self.knot_class.declared_description()
        doc = (self.knot_class.__doc__ or "").strip()
        first = doc.split("\n\n")[0].strip()
        return first or self.name

    def declaration(self) -> ToolDeclaration:
        """The provider-neutral ``{name, description, parameters}`` envelope.

        ``parameters`` is the override given at construction, else the knot
        class's ``input_json_schema()`` without the bound and hidden inputs;
        an empty ``required`` list is omitted, as the wire shape expects.
        """
        if self._parameters is not None:
            parameters: dict[str, Any] = copy.deepcopy(self._parameters)
        else:
            schema = self.knot_class.input_json_schema()
            hidden = set(self._bound) | self._hidden
            properties = {
                key: dict(value) if isinstance(value, Mapping) else value
                for key, value in schema.get("properties", {}).items()
                if key not in hidden
            }
            for key, value in self._defaults.items():
                if key in properties and isinstance(properties[key], dict):
                    properties[key]["default"] = value
            required = [
                key
                for key in schema.get("required", [])
                if key not in hidden and key not in self._defaults
            ]
            parameters = {"type": "object", "properties": properties}
            if required:
                parameters["required"] = required
            if "$defs" in schema:
                parameters["$defs"] = schema["$defs"]
        return ToolDeclaration(name=self.name, description=self.description, parameters=parameters)

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """The declaration's JSON ``parameters`` object (``declaration().parameters``)."""
        return self.declaration().parameters

    @property
    def permissions(self) -> ToolPermissions:
        """Permission / scope metadata for this capability."""
        if issubclass(self.knot_class, Tool):
            return self.knot_class.permissions
        return ToolPermissions()

    def requires_approval(self) -> bool:
        """Whether a call must be approved by a human (from :attr:`permissions`)."""
        return self.permissions.approval_required

    @property
    def streaming(self) -> bool:
        """Whether :meth:`stream` yields incremental output."""
        if issubclass(self.knot_class, Tool):
            return self.knot_class.streaming
        return False

    @property
    def stateful(self) -> bool:
        """Whether this capability carries injected state across calls."""
        return False

    @property
    def state(self) -> Any | None:
        """The injected state/resource object, or ``None``."""
        return None

    def stream(self, arguments: Mapping[str, Any]) -> AsyncIterator[Any]:
        """Return an async iterator of partial results for ``arguments``.

        Raises:
            TypeError: If this is not a streaming capability.
        """
        if issubclass(self.knot_class, Tool):
            return self.knot_class.stream({**self._bound, **self.resolve_arguments(arguments)})
        raise TypeError(f"tool {self.name!r} is not a streaming tool")

    async def collect_stream(self, arguments: Mapping[str, Any]) -> list[Any]:
        """Drain :meth:`stream` for ``arguments`` into a list of chunks."""
        return [chunk async for chunk in self.stream(arguments)]

    def describe(self) -> dict[str, Any]:
        """The declaration payload plus the non-default ``permissions`` fragment."""
        descriptor: dict[str, Any] = self.declaration().to_payload()
        fragment = self.permissions.as_schema_fragment()
        if fragment:
            descriptor["permissions"] = fragment
        return descriptor

    # ------------------------------------------------------------ one call

    def __call__(self, **kwargs: Any) -> Knot:
        """Construct one call: the bound inputs plus *kwargs* (``_config`` included).

        A declared input neither bound nor supplied takes the default its
        ``process()`` parameter declares — the model omits optional arguments
        routinely, and core requires every hinted input at construction.
        """
        merged = {**self._defaults, **self._bound, **kwargs}
        if self._packs_arguments:
            framework = {
                key: merged.pop(key) for key in tuple(Knot._reserved_kwargs) if key in merged
            }
            return self.knot_class(arguments=merged, **framework)
        for name, default in self._process_defaults().items():
            merged.setdefault(name, default)
        return self.knot_class(**merged)

    def _process_defaults(self) -> dict[str, Any]:
        """Name -> default for every ``process()`` parameter that declares one."""
        if self.knot_class._input_schema_override is not None:
            return {}
        return {
            name: parameter.default
            for name, parameter in inspect.signature(self.knot_class.process).parameters.items()
            if parameter.default is not inspect.Parameter.empty
            and parameter.kind
            not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
        }

    def resolve_arguments(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        """Return *arguments* with a lone ReAct-style alias moved onto the primary parameter."""
        resolved = dict(arguments)
        if self._packs_arguments:
            return resolved
        parameters = self.declaration().parameters
        declared = parameters.get("properties", {})
        required = parameters.get("required", [])
        primary = required[0] if required else next(iter(declared), None)
        if primary is None or primary in resolved:
            return resolved
        for alias in self._aliases:
            if alias in resolved and alias not in declared:
                resolved[primary] = resolved.pop(alias)
                break
        return resolved

    def validate_arguments(self, arguments: Mapping[str, Any]) -> dict[str, str]:
        """Return ``{argument: reason}`` for every way *arguments* violate the declaration.

        Required names absent are ``"missing_required"``; names the
        declaration does not know are ``"unexpected_property"`` (a knot
        accepts only declared inputs); a value the property's adapter refuses
        is ``"expected:<type>,got:<python type>"``.  Empty when valid.
        """
        if not isinstance(arguments, Mapping):
            return {"arguments": "expected:object"}
        schema = self.declaration().parameters
        properties = schema.get("properties", {})
        detail: dict[str, str] = {}
        for required in schema.get("required", []):
            if required not in arguments:
                detail[str(required)] = "missing_required"
        # A knot accepts only declared inputs; a deprecated invoke-shaped tool
        # takes the whole mapping, so there an extra key is refused only when
        # its schema says ``additionalProperties: false``.
        refuse_unknown = not self._packs_arguments or schema.get("additionalProperties") is False
        if refuse_unknown:
            for key in arguments:
                if key not in properties:
                    detail.setdefault(str(key), "unexpected_property")
        try:
            adapters = JsonSchemaTypeBuilder.input_adapters(schema)
        except Exception:
            adapters = {}
        for key, value in arguments.items():
            if key in detail:
                continue
            adapter = adapters.get(key)
            if adapter is None:
                continue
            fragment = properties.get(key, {})
            expected = fragment.get("type") if isinstance(fragment, Mapping) else None
            # JSON Schema's ``integer``/``number`` exclude booleans; pydantic's lax
            # mode would coerce ``True`` to ``1``, so the check is made here.
            if isinstance(value, bool) and expected in ("integer", "number"):
                detail[str(key)] = f"expected:{expected},got:bool"
                continue
            try:
                adapter.validate_python(value)
            except ValidationError:
                enum = fragment.get("enum") if isinstance(fragment, Mapping) else None
                if isinstance(enum, list):
                    expected_name = f"one of {enum!r}"
                elif isinstance(expected, str):
                    expected_name = expected
                else:
                    expected_name = "declared type"
                detail[str(key)] = f"expected:{expected_name},got:{type(value).__name__}"
        return detail

    @staticmethod
    def knot_id_for(call_id: str) -> str:
        """The knot id a call runs under: ``call_id`` when it is a valid id, else a hash of it."""
        try:
            KnotConfig(id=call_id)
        except ValueError:
            digest = hashlib.sha256(str(call_id).encode("utf-8")).hexdigest()[:16]
            return f"call-{digest}"
        return call_id

    def for_call(
        self,
        call: ToolCall,
        *,
        knot_id: str | None = None,
        timeout: float | None = None,
        retry: KnotRetryPolicy | None = None,
        concurrency_group: str | None = None,
        approval_hook: Any = None,
        tapestry: Any = None,
    ) -> Knot:
        """Construct the knot that executes *call*.

        Args:
            call: The model's decision: tool name, arguments, call id.
            knot_id: The knot id to run under; defaults to
                ``knot_id_for(call.call_id)`` (a batch with a repeated call id
                passes distinct ids).
            timeout: ``KnotConfig.timeout`` for the call.
            retry: ``KnotConfig.retry`` for the call.
            concurrency_group: ``KnotConfig.concurrency_group`` for the call.
            approval_hook: The
                :class:`~pirn_agents.agent.approval_hook.ApprovalHook` to
                consult when this capability's permissions require approval
                (PIR-865); ``None`` uses the auto-approving default. Ignored
                for a capability that does not require approval. Typed
                ``Any`` for the same reason ``ParallelToolExecutor(hook=...)``
                is: a bare, non-pydantic class core's eager per-input
                ``TypeAdapter`` build cannot schema.
            tapestry: Explicit tapestry to register with, as for any knot.

        Returns:
            One call, registered in the active (or given) tapestry. When the
            capability requires approval, a
            :class:`~pirn_agents.agent.tool_approval_check.ToolApprovalCheck`
            behind a core ``Gate`` is wired in front of it (see
            :meth:`_approval_gate`), so a denied call's own outcome is a core
            ``Skipped`` — the tool's ``process()`` is never called — instead
            of the call raising.

        Raises:
            ToolArgumentValidationError: If the arguments do not satisfy the
                declaration or core refuses them at construction.
        """
        arguments = self.resolve_arguments(call.arguments)
        detail = self.validate_arguments(arguments)
        if detail:
            raise ToolArgumentValidationError(self.name, detail, call.call_id)
        resolved_id = knot_id if knot_id is not None else self.knot_id_for(call.call_id)
        config = KnotConfig(
            id=resolved_id, timeout=timeout, retry=retry, concurrency_group=concurrency_group
        )
        gate = (
            self._approval_gate(resolved_id, arguments, approval_hook, tapestry)
            if self.requires_approval()
            else None
        )
        # An extra Knot-valued kwarg no declared input names is accepted as
        # an *implicit* parent (Knot._validate_kwargs_against_signature) for
        # either call shape below: a legacy packed-arguments knot's sole
        # declared input is the schema's "arguments" object, and an ordinary
        # tool's is whatever its own process() names, but both process()
        # signatures end with "**_: Any" (a framework requirement for every
        # knot), which is exactly what absorbs an implicit parent's resolved
        # value. Passed as its own keyword rather than folded into the
        # packed-arguments dict, so the value a capability's own process()
        # actually reads is never touched by this wiring.
        call_kwargs: dict[str, Any] = dict(arguments)
        if gate is not None:
            call_kwargs["_approval_gate"] = gate
        try:
            if self._packs_arguments:
                framework: dict[str, Any] = {"_config": config}
                if tapestry is not None:
                    framework["tapestry"] = tapestry
                if gate is not None:
                    framework["_approval_gate"] = gate
                merged = {**self._defaults, **self._bound, **arguments}
                return self.knot_class(arguments=merged, **framework)
            if tapestry is not None:
                return self(**call_kwargs, _config=config, tapestry=tapestry)
            return self(**call_kwargs, _config=config)
        except TypeError as exc:
            raise ToolArgumentValidationError(
                self.name, {"arguments": str(exc)}, call.call_id
            ) from exc

    def _approval_gate(
        self,
        knot_id: str,
        arguments: Mapping[str, Any],
        approval_hook: Any,
        tapestry: Any,
    ) -> Knot:
        """Build the ``Gate``/``ToolApprovalCheck`` pair guarding an approval-required call.

        The gate's ``input`` is a :class:`~pirn.core.parameter.Parameter`
        carrying *arguments* — "the call's arguments knot" from the ADR — so
        it is also what :class:`~pirn_agents.agent.tool_approval_check.ToolApprovalCheck`
        reads. The returned gate is wired by :meth:`for_call` as an
        *implicit* parent of the constructed call — an extra ``Knot`` kwarg
        the call does not declare by name but that core still requires to
        resolve, and skip-propagate from, before ``process()`` runs (an
        extra ``Knot``-valued kwarg is accepted this way whenever
        ``process()`` ends with ``**_: Any``, which every tool's does) — so a
        denial reaches the call without changing any capability's own
        declared inputs or the value its ``process()`` actually receives.

        Local import: :mod:`pirn_agents.agent.tool_approval_check` imports
        this module (:class:`ToolFactory`) already, so a module-level import
        here would cycle.
        """
        from pirn_agents.agent.tool_approval_check import ToolApprovalCheck

        tapestry_kwargs: dict[str, Any] = {} if tapestry is None else {"tapestry": tapestry}
        call_arguments = Parameter(
            f"{knot_id}:approval-args",
            dict,
            default=dict(arguments),
            _config=KnotConfig(id=f"{knot_id}:approval-args"),
            **tapestry_kwargs,
        )
        check = ToolApprovalCheck(
            tool=self,
            arguments=call_arguments,
            hook=approval_hook,
            _config=KnotConfig(id=f"{knot_id}:approval-check"),
            **tapestry_kwargs,
        )
        return Gate(
            input=call_arguments,
            check=check,
            _config=KnotConfig(id=f"{knot_id}:approval-gate"),
            **tapestry_kwargs,
        )

    async def run_call(self, call: ToolCall, *, approval_hook: Any = None) -> Result[Any]:
        """Construct *call* and run it, outside any enclosing engine run.

        For callers with no tapestry to run in — the deprecated ``invoke``
        shim, a test.  The knot is registered with a throwaway tapestry,
        never the ambient one, so a caller inside another knot's ``process()``
        does not also wire it into that knot's inner graph.

        A capability that does not require approval is awaited directly —
        ``knot({})`` — exactly as before; it has no real parent to resolve
        (its arguments are plain config values), so nothing here changes for
        the overwhelmingly common case. One that *does* require approval
        (PIR-865) has a genuine parent — the
        :meth:`_approval_gate`-built ``Gate`` — that a bare ``knot({})`` call
        would silently never resolve (it only fills in parents a caller
        supplies in ``parent_results``, and does not walk the graph itself);
        such a call is run through the throwaway tapestry's own engine
        (``Tapestry.run``) instead, so the gate is actually evaluated and a
        denial really does skip the call rather than running it anyway.
        """
        from pirn.tapestry import Tapestry  # local: avoids an import cycle

        tapestry = Tapestry()
        knot = self.for_call(call, approval_hook=approval_hook, tapestry=tapestry)
        if not self.requires_approval():
            return await knot({})
        from pirn_agents.tools.tool_call_codec import ToolCallCodec  # local: avoids an import cycle

        run_result = await tapestry.run(terminals=knot)
        return ToolCallCodec.outcomes_of(run_result, [call])[call.call_id]

    # ------------------------------------------------------------ pydantic

    @classmethod
    def _validate_candidate(cls, value: Any) -> ToolFactory:
        try:
            return cls.of(value)
        except TypeError as exc:
            raise ValueError(str(exc)) from exc

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Accept a factory, a knot class/factory, a configured knot or a legacy tool.

        A knot input annotated ``ToolFactory`` therefore takes any spelling of
        a capability and ``process()`` always receives a factory — the
        coercion is validation, not a separate normalisation step.
        """
        return core_schema.no_info_plain_validator_function(
            cls._validate_candidate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: v._pirn_audit_dict(),
                when_used="always",
            ),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Content identity: the definition's reference when it has one, else identity-keyed."""
        reference = DefinitionReference.of(self.knot_class)
        return {
            "tool": self.name,
            "definition": (
                reference
                if reference is not None
                else f"<{self.knot_class.__qualname__}@{self._pirn_identity_token()}>"
            ),
            "bound": {key: repr(self._bound[key]) for key in sorted(self._bound)},
            "defaults": {key: repr(self._defaults[key]) for key in sorted(self._defaults)},
        }

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} name={self.name!r} knot_class={self.knot_class.__qualname__}>"
        )
