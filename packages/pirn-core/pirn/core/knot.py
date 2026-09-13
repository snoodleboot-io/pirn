"""The ``Knot`` — pirn's unit of work.

Constructor convention (Phase 2)
--------------------------------
A knot is constructed with kwargs that are introspected against the
knot's ``process`` method signature.  For each kwarg:

* If the value is itself a ``Knot``, it becomes a **parent** — this knot
  depends on the other knot's output.
* Otherwise, the value is **config** — a constant used at run time.

Framework metadata (id, validate_io, error_policy) goes through a single
reserved kwarg: ``_config=KnotConfig(...)``.  This keeps the framework
namespace separate from the user's process-parameter namespace.

Required at construction
------------------------
* Every kwarg named in the knot's ``process`` signature must be supplied.
  Missing parents/configs fail at construction, not at run time.
* Every kwarg must match a parameter name on ``process``.  Typos fail at
  construction.
* ``_config.id`` is required.  No auto-generated ids.

Self-registration
-----------------
If a ``Tapestry`` context is active (created via ``with Tapestry() as t:``),
newly constructed knots register themselves with it.  This is how the
tapestry comes to know what knots exist without any explicit ``add()``
ceremony.  Outside a context, a ``tapestry=`` kwarg can be passed
explicitly.
"""

from __future__ import annotations

import asyncio
import copy
import inspect
import json
import types as _types
import warnings
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar, Union, get_args, get_origin, get_type_hints

from pydantic import TypeAdapter, ValidationError

from pirn.core.dict_map import DictMap
from pirn.core.err import Err
from pirn.core.json_schema_type_builder import JsonSchemaTypeBuilder
from pirn.core.knot_config import KnotConfig
from pirn.core.map import Map
from pirn.core.map_type_error import MapTypeError
from pirn.core.ok import Ok
from pirn.core.result import Result
from pirn.core.skipped import Skipped
from pirn.core.zip_map import ZipMap
from pirn.managers.exception_record import ExceptionRecord

if TYPE_CHECKING:
    from pirn.tapestry import Tapestry


class Knot:
    """Abstract base class for all units of work in a pirn pipeline.

    Subclass and implement ``process``.  The framework's ``__call__`` is
    internal; users do not invoke or override it.
    """

    # Class-level default; set to True on each instance at the end of
    # __init__.  Having it as a class attribute means __setattr__ can
    # read it directly without falling back to getattr() probing for
    # instances under construction.
    _frozen: bool = False

    _reserved_kwargs: frozenset[str] = frozenset({"_config", "tapestry"})

    # Opt-in, per-class: declare ``process`` in the gradual parameter form
    # ``(*args: Any, **kwargs: Any)`` so a type checker skips the parameter half
    # of its override check for every subclass, while still checking the return
    # type (PIR-833).  Only an *abstract* mid-tree base that exists to narrow the
    # return type should set it — the engine binds named inputs dynamically, so
    # a concrete knot's parameter list can never be substitutable for its base's
    # and the diagnostic is a false positive by construction.
    #
    # ``__init_subclass__`` reads it from ``cls.__dict__``, never from the MRO,
    # so the opt-in cannot be inherited: a subclass of an opted-in base is still
    # refused if it declares ``*args`` in ``process``.
    _dynamic_process_signature: ClassVar[bool] = False

    # Populated by __init_subclass__ for each class that defines process().
    # Maps param name -> scalar type extracted from ``Knot | T`` union hints.
    _coercible_params: dict[str, Any] = {}  # noqa: RUF012

    # A JSON object schema declaring the inputs of a knot that has no Python
    # signature to introspect -- an MCP-declared tool, an OpenAPI operation
    # (ADR agents-speaks-core, WS0).  When set, the schema's ``properties``
    # are the declared inputs, its ``required`` the ones construction must
    # supply, its ``default``s fill the rest, and each property's fragment is
    # turned into the ``TypeAdapter`` that ``validate_io`` applies
    # (``JsonSchemaTypeBuilder``), so a schema-declared knot is validated by
    # exactly the machinery a hinted one is.  ``process`` is then
    # ``(self, **kwargs)`` and receives the validated inputs by name.  Set by
    # ``KnotFactory.from_schema``; ``input_json_schema()`` returns it as is.
    _input_schema_override: ClassVar[Mapping[str, Any] | None] = None

    @staticmethod
    def _is_knot_cls(candidate: Any) -> bool:
        """Return True if *candidate* is Knot or a subclass of Knot."""
        try:
            return isinstance(candidate, type) and issubclass(candidate, Knot)
        except TypeError:
            return False

    @staticmethod
    def _extract_coercible_type(hint: Any) -> tuple[Any, Any] | None:
        """Return ``(coerce_type, adapter_type)`` for a ``Knot | T`` union hint.

        *coerce_type* is the non-Knot, non-NoneType member — used as the
        ``type_`` when wrapping a scalar in a ``Parameter``.
        *adapter_type* is the full union with Knot removed (NoneType kept) —
        used as the pydantic validation type so ``None`` is accepted when the
        original hint included it.

        Returns ``None`` if the hint is not a Union that contains Knot alongside
        at least one non-Knot, non-NoneType member.
        """
        origin = get_origin(hint)
        args: tuple[Any, ...] = ()

        if origin is Union:
            args = get_args(hint)
        else:
            try:
                if isinstance(hint, _types.UnionType):
                    args = get_args(hint)
            except AttributeError:
                pass

        if not args:
            return None

        has_knot = any(Knot._is_knot_cls(a) for a in args)
        if not has_knot:
            return None

        non_knot_non_none = [a for a in args if a is not type(None) and not Knot._is_knot_cls(a)]
        if not non_knot_non_none:
            return None

        coerce_type = non_knot_non_none[0] if len(non_knot_non_none) == 1 else Any

        # adapter_type: all args except Knot subclasses — preserves None.
        adapter_args = [a for a in args if not Knot._is_knot_cls(a)]
        if len(adapter_args) == 1:
            adapter_type: Any = adapter_args[0]
        elif adapter_args:
            adapter_type = Union[tuple(adapter_args)]  # noqa: UP007
        else:
            adapter_type = coerce_type

        return coerce_type, adapter_type

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "process" in cls.__dict__:
            # follow_wrapped=False: inspect the actual method body, not the
            # user's original function via __wrapped__.  @knot-generated methods
            # have **kwargs in their body; user class overrides must have **_.
            sig = inspect.signature(cls.__dict__["process"], follow_wrapped=False)
            has_var_pos = False
            has_var_kw = False
            for param in sig.parameters.values():
                if param.kind == inspect.Parameter.VAR_POSITIONAL:
                    has_var_pos = True
                if param.kind == inspect.Parameter.VAR_KEYWORD:
                    has_var_kw = True
            if has_var_pos and not cls.__dict__.get("_dynamic_process_signature", False):
                raise TypeError(
                    f"{cls.__name__}.process may not declare *args; "
                    "pirn calls process() exclusively with keyword arguments"
                )
            if not has_var_kw:
                raise TypeError(
                    f"{cls.__name__}.process must include '**_: Any' to absorb "
                    "implicit dependencies; add it after all named parameters"
                )

            # Cache which params have ``Knot | T`` union hints so __init__ can
            # auto-coerce scalar values to Parameter nodes without the author
            # needing to call any explicit helper.
            try:
                hints = get_type_hints(cls.__dict__["process"])
            except Exception as exc:
                warnings.warn(
                    f"{cls.__name__}.process: get_type_hints() failed ({exc!r}); "
                    "Knot | T scalar auto-coercion is disabled for this class. "
                    "This usually means a forward-referenced annotation cannot "
                    "be resolved (e.g. a name only imported under TYPE_CHECKING).",
                    stacklevel=2,
                )
                hints = {}
            coercible: dict[str, Any] = {}
            for pname, hint in hints.items():
                if pname in ("self", "return"):
                    continue
                result = cls._extract_coercible_type(hint)
                if result is not None:
                    coercible[pname] = result  # (coerce_type, adapter_type)
            cls._coercible_params = coercible

    def __init__(self, **kwargs: Any) -> None:
        config, explicit_tapestry, kwargs = self._extract_framework_kwargs(kwargs)
        mapped_inputs, kwargs = self._extract_map_markers(kwargs, config)

        # Validate the remaining kwargs against process()'s signature -- or,
        # for a schema-declared knot, against the declared schema.
        # follow_wrapped=True: for @knot classes, inspect the user's original
        # function so declared input names reflect its real parameter names.
        sig = self._process_signature()
        schema = type(self)._input_schema_override
        if schema is not None:
            declared = JsonSchemaTypeBuilder.declared(schema)
            required = JsonSchemaTypeBuilder.required(schema)
        else:
            declared = self._declared_input_names(sig)
            required = declared
        accepts_implicit = self._has_var_keyword(sig)
        self._validate_kwargs_against_signature(
            kwargs, declared, accepts_implicit, config, required=required
        )
        if schema is not None:
            kwargs = {**JsonSchemaTypeBuilder.defaults(schema), **kwargs}

        kwargs = self._coerce_scalar_parameters(kwargs, config, explicit_tapestry)
        parents, config_values = self._partition_parents_and_config(kwargs)

        # Build adapters for input/output validation now (one-time cost).
        input_adapters, output_adapter = self._build_adapters(sig)
        config_values = self._validate_config_values(config_values, input_adapters, config)

        # Stash everything and self-register with the active tapestry (if
        # any) or with the explicitly passed one.  Done last so the knot is
        # fully built before the tapestry sees it.
        self._bootstrap(
            config=config,
            parents=parents,
            config_values=config_values,
            input_adapters=input_adapters,
            output_adapter=output_adapter,
            mapped_inputs=mapped_inputs,
            tapestry=explicit_tapestry,
        )

        self._frozen = True

    # --------------------------------------------------- __init__ steps

    @classmethod
    def _extract_framework_kwargs(
        cls, kwargs: dict[str, Any]
    ) -> tuple[KnotConfig, Tapestry | None, dict[str, Any]]:
        """Pull ``_config`` and ``tapestry`` out of the constructor kwargs.

        Returns the validated ``KnotConfig``, the explicit tapestry (or
        ``None``), and the remaining kwargs with both reserved names removed.
        """
        kwargs = dict(kwargs)
        config: KnotConfig = kwargs.pop("_config", None)  # type: ignore[assignment]  # None is narrowed to KnotConfig two lines below
        if config is None:
            raise TypeError(
                f"{cls.__name__} requires _config=KnotConfig(id=...).  "
                "Pirn requires explicit knot ids; nothing is auto-generated."
            )
        if not isinstance(config, KnotConfig):
            raise TypeError(
                f"{cls.__name__}: _config must be a KnotConfig instance, "
                f"got {type(config).__name__}"
            )
        explicit_tapestry: Tapestry | None = kwargs.pop("tapestry", None)
        return config, explicit_tapestry, kwargs

    @classmethod
    def _extract_map_markers(
        cls, kwargs: dict[str, Any], config: KnotConfig
    ) -> tuple[dict[str, type], dict[str, Any]]:
        """Detect and extract distribution markers (``Map``, ``ZipMap``, ``DictMap``).

        Done before signature validation so markers on declared inputs are
        treated as Knot parents rather than non-Knot config errors. Returns
        the name -> marker-type mapping and the kwargs with each marker
        replaced by its underlying source knot.
        """
        mapped_inputs: dict[str, type] = {}
        marker_sources: dict[str, Any] = {}
        resolved_kwargs: dict[str, Any] = {}
        for name, value in kwargs.items():
            if isinstance(value, (Map, ZipMap, DictMap)):
                mapped_inputs[name] = type(value)
                marker_sources[name] = value.source
                resolved_kwargs[name] = value.source
            else:
                resolved_kwargs[name] = value

        if mapped_inputs:
            cls._validate_marker_consistency(mapped_inputs, marker_sources, config)

        return mapped_inputs, resolved_kwargs

    @classmethod
    def _validate_marker_consistency(
        cls,
        mapped_inputs: dict[str, type],
        marker_sources: dict[str, Any],
        config: KnotConfig,
    ) -> None:
        marker_types = set(mapped_inputs.values())
        if len(marker_types) > 1:
            raise TypeError(
                f"{cls.__name__}({config.id!r}): cannot mix "
                "Map, ZipMap, and DictMap markers on the same knot"
            )
        sole_type = next(iter(marker_types))
        if sole_type is Map and len(mapped_inputs) > 1:
            raise TypeError(
                f"{cls.__name__}({config.id!r}): multiple Map-annotated "
                "inputs would produce a cross-product; use ZipMap to zip "
                "multiple collections element-wise"
            )
        if sole_type is DictMap and len(mapped_inputs) != 2:
            raise TypeError(
                f"{cls.__name__}({config.id!r}): DictMap requires exactly "
                "two annotated inputs (key-receiver and value-receiver)"
            )
        if sole_type is DictMap:
            dict_sources = list(marker_sources.values())
            if dict_sources[0] is not dict_sources[1]:
                raise TypeError(
                    f"{cls.__name__}({config.id!r}): both DictMap inputs "
                    "must reference the same source knot"
                )

    @classmethod
    def _validate_kwargs_against_signature(
        cls,
        kwargs: dict[str, Any],
        declared: set[str],
        accepts_implicit: bool,
        config: KnotConfig,
        required: set[str] | None = None,
    ) -> None:
        """Reject unknown or missing kwargs against process()'s declared inputs.

        Extra Knot-valued kwargs are implicit parents (ordering dependencies
        whose output is not used directly) when ``process()`` accepts
        ``**kwargs``; extra non-Knot ones are always errors.  *required* is
        the subset of *declared* that must be supplied; it defaults to all of
        them, and a schema-declared knot narrows it to the schema's
        ``required`` list.
        """
        unknown = set(kwargs) - declared - cls._reserved_kwargs
        if unknown:
            if accepts_implicit:
                bad_config = {k for k in unknown if not isinstance(kwargs[k], Knot)}
                if bad_config:
                    raise TypeError(
                        f"{cls.__name__}({config.id!r}): unknown non-Knot "
                        f"kwarg(s) {sorted(bad_config)!r}; only Knot parents may "
                        "be passed as implicit dependencies"
                    )
                # Remaining unknowns are all Knot-valued — accepted as implicit parents.
            else:
                raise TypeError(
                    f"{cls.__name__}({config.id!r}): unknown kwarg(s) "
                    f"{sorted(unknown)!r}; declared inputs are {sorted(declared)!r}. "
                    "To wire implicit dependencies add '**_: Any' to process()"
                )

        missing = (declared if required is None else required) - set(kwargs)
        if missing:
            raise TypeError(
                f"{cls.__name__}({config.id!r}): missing required input(s) {sorted(missing)!r}"
            )

    @classmethod
    def _coerce_scalar_parameters(
        cls,
        kwargs: dict[str, Any],
        config: KnotConfig,
        explicit_tapestry: Tapestry | None,
    ) -> dict[str, Any]:
        """Auto-coerce scalars for params annotated ``Knot | T``.

        Wraps the scalar in a ``Parameter(default=value)`` so it becomes a
        real graph node with lineage, rather than invisible config.
        """
        coercible = cls._coercible_params
        if not coercible:
            return kwargs

        from pirn.core.parameter import Parameter  # local: avoids circular import

        kwargs = dict(kwargs)
        for pname, (coerce_type, _adapter_type) in coercible.items():
            if pname not in kwargs:
                continue
            value = kwargs[pname]
            if value is None or isinstance(value, Knot):
                continue
            kwargs[pname] = Parameter(
                name=f"{config.id}__{pname}",
                type_=coerce_type,
                default=value,
                _config=KnotConfig(id=f"auto:{config.id}:{pname}"),
                tapestry=explicit_tapestry,
            )
        return kwargs

    @staticmethod
    def _partition_parents_and_config(
        kwargs: dict[str, Any],
    ) -> tuple[dict[str, Knot], dict[str, Any]]:
        """Split kwargs into Knot-valued parents and plain config values.

        Explicit parents/configs (named in ``process()``) and implicit
        parents (extra Knot kwargs absorbed by ``**_``) are both partitioned
        the same way: by whether the value is a ``Knot``.
        """
        parents: dict[str, Knot] = {}
        config_values: dict[str, Any] = {}
        for name, value in kwargs.items():
            if isinstance(value, Knot):
                parents[name] = value  # explicit and implicit parents both stored here
            else:
                config_values[name] = value
        return parents, config_values

    @classmethod
    def _validate_config_values(
        cls,
        config_values: dict[str, Any],
        input_adapters: dict[str, TypeAdapter],
        config: KnotConfig,
    ) -> dict[str, Any]:
        """Validate config values against their declared types eagerly.

        They're constants, so this can happen at construction time rather
        than waiting for the first run.
        """
        if not config.validate_io:
            return config_values

        config_values = dict(config_values)
        for name, value in config_values.items():
            adapter = input_adapters.get(name)
            if adapter is None:
                continue
            try:
                config_values[name] = adapter.validate_python(value)
            except ValidationError as exc:
                raise TypeError(
                    f"{cls.__name__}({config.id!r}).{name}: config value failed validation: {exc}"
                ) from exc
        return config_values

    # ------------------------------------------------------- bootstrap

    def _bootstrap(
        self,
        *,
        config: KnotConfig,
        parents: Mapping[str, Knot],
        config_values: Mapping[str, Any] | None = None,
        input_adapters: Mapping[str, TypeAdapter] | None = None,
        output_adapter: TypeAdapter | None = None,
        mapped_inputs: Mapping[str, type] | None = None,
        tapestry: Tapestry | None = None,
    ) -> None:
        """Stash the ``_mutable_`` slots and register with the tapestry.

        Framework primitives that cannot go through the standard
        ``Knot.__init__`` introspection (``Aggregator``, ``Reduce``, ``Gate``,
        ``Branch``, ``BranchOutput``, ``Parameter``) construct their own
        parent/config wiring by hand and previously duplicated the block that
        stashes it onto ``_mutable_`` slots and self-registers with the
        active tapestry. Six copies of that block drifted independently as
        the slot set grew (``_mutable_fan_out_extra`` was added to some but
        not all). This method is the one place that does it, so a new slot
        or a change to registration order is written once.

        Callers still set any additional ``_mutable_`` state of their own
        (e.g. ``Gate``'s ``_mutable_predicate``) and must set
        ``self._frozen = True`` themselves once construction is complete —
        this method deliberately does not freeze, since some callers stash
        further state after calling it.

        Args:
            config: The knot's framework configuration.
            parents: Name to parent-knot mapping.
            config_values: Name to constant-value mapping. Defaults to empty.
            input_adapters: Name to ``TypeAdapter`` mapping for input
                validation. Defaults to empty (no input validation).
            output_adapter: ``TypeAdapter`` for output validation, or
                ``None`` to skip it.
            mapped_inputs: Name to marker-type mapping for fan-out (``Map``,
                ``ZipMap``, ``DictMap``) inputs. Defaults to empty.
            tapestry: Explicit tapestry to register with. When ``None``, the
                active context-var tapestry is used, matching the standard
                ``Knot.__init__`` self-registration behaviour.
        """
        self._mutable_config = config
        self._mutable_parents = dict(parents)
        self._mutable_config_values = dict(config_values) if config_values else {}
        self._mutable_input_adapters = dict(input_adapters) if input_adapters else {}
        self._mutable_output_adapter = output_adapter
        self._mutable_mapped_inputs = dict(mapped_inputs) if mapped_inputs else {}
        self._mutable_fan_out_extra: dict[str, Any] = {}
        # Written by the engine onto the run-scoped copy it dispatched --
        # e.g. the attempt count under ``KnotConfig.retry`` -- and merged into
        # ``lineage_extra``.  Always reassigned, never mutated in place, so a
        # shallow ``run_scoped_copy`` never shares it with the graph knot.
        self._mutable_dispatch_extra: dict[str, Any] = {}

        from pirn.tapestry import _current_tapestry

        target_tapestry = tapestry or _current_tapestry.get(None)
        if target_tapestry is not None:
            target_tapestry.register(self)

    # ----------------------------------------------------------- lineage

    def lineage_extra(self) -> dict[str, Any]:
        """Return structured metadata to merge into this knot's lineage record.

        Override in subclasses to surface execution-time context (e.g. which
        branch was selected, predicate outcome, inner run id).  The base
        implementation returns fan-out metadata when a map operation ran,
        otherwise an empty dict.

        Called by the engine after ``__call__`` returns on the **run-scoped
        copy** it dispatched, so an override may read execution-time state
        that ``process()``/``__call__`` stashed on ``self`` -- that state
        belongs to one run and cannot be seen by another.

        Called by the engine after ``__call__`` returns; the returned dict is
        merged into ``KnotLineage.extra``.
        """
        return {**self._mutable_fan_out_extra, **self._mutable_dispatch_extra}

    def run_scoped_copy(self) -> Knot:
        """Return a copy of this knot for one run to execute and mutate.

        A ``Tapestry`` is routinely built once at startup and used to serve
        many concurrent requests, so its knots are shared across runs.
        Several of them publish run-derived metadata by writing it onto
        ``self`` for ``lineage_extra`` to read back -- the selected branch, a
        gate's predicate outcome, fan-out element counts, a ``SubTapestry``'s
        ``inner_run_id``.  The engine reads that slot only after awaiting the
        dispatch, and a sibling run finishing inside that window overwrote it,
        so runs recorded each other's answers (PIR-809).  Nothing failed: the
        outputs stayed correct and each record still carried its own run id,
        which is what made the wrong ``inner_run_id`` -- the only navigation
        path from an outer lineage record to its child run -- so misleading.

        Giving each run its own copy to execute fixes every such slot at once,
        including ones added later, instead of defending each site
        individually.  The copy keeps this knot's ``knot_id``, config, parents
        and adapters, so the engine's id-keyed bookkeeping (results, handles,
        status, lineage) is unaffected, and it deliberately does not register
        with a tapestry: it belongs to one dispatch, not to the graph.  The
        shared knot is never executed and so is never mutated, which also
        closes the stale-read path between *sequential* runs.

        Mutating ``self`` inside ``process()`` still works within a run -- a
        fan-out calls ``process()`` many times on the same copy.  Only
        accumulation *across* runs is dropped, which was never safe on a
        shared graph.

        Override in a subclass whose per-run state needs deeper isolation
        than a shallow copy provides.

        Returns:
            A copy of this knot for a single dispatch, leaving ``self``
            untouched.
        """
        return copy.copy(self)

    # ------------------------------------------------------------ schema

    @classmethod
    def input_json_schema(cls) -> dict[str, Any]:
        """Return the JSON schema of this knot's ``process()`` inputs.

        The inverse of ``_input_schema_override``: the same hints
        ``_build_adapters`` validates with, rendered as one object schema.
        This is what a model-facing declaration of the knot derives from
        (ADR agents-speaks-core, WS0).

        Algorithm:
            1. A schema-declared knot returns its declaration unchanged.
            2. Otherwise, for each named ``process()`` parameter (``self``,
               ``*args`` and ``**_`` excluded), take the validation
               annotation ``_build_adapters`` would use -- ``T`` for a
               ``Knot | T`` hint -- and skip it when it is Knot-typed or a
               ``PirnOpaqueValue`` (a live resource is wired, never
               supplied by a caller); an unannotated parameter is ``{}``.
            3. Render each remaining annotation with
               ``TypeAdapter(...).json_schema()``, hoisting any ``$defs``
               to the top level, and record a JSON-serialisable default.
            4. Parameters without a default are ``required``.

        Returns:
            ``{"type": "object", "properties": {...}, "required": [...]}``
            plus ``"$defs"`` when a property's schema needs them.
        """
        override = cls._input_schema_override
        if override is not None:
            return json.loads(json.dumps(override))
        sig = cls._process_signature()
        hints = cls._process_hints(sig)
        properties: dict[str, Any] = {}
        required: list[str] = []
        defs: dict[str, Any] = {}
        for name, annotation in cls._input_annotations(sig, hints).items():
            if cls._is_wired_only(annotation):
                continue
            fragment: dict[str, Any] = (
                {} if annotation is Any else TypeAdapter(annotation).json_schema()
            )
            defs.update(fragment.pop("$defs", {}))
            default = sig.parameters[name].default
            if default is inspect.Parameter.empty:
                required.append(name)
            elif cls._is_json_value(default):
                fragment["default"] = default
            properties[name] = fragment
        schema: dict[str, Any] = {"type": "object", "properties": properties, "required": required}
        if defs:
            schema["$defs"] = defs
        return schema

    @staticmethod
    def _is_json_value(value: Any) -> bool:
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            return False
        return True

    @classmethod
    def _is_wired_only(cls, annotation: Any) -> bool:
        """Whether *annotation* names something only a parent knot can supply."""
        from pirn.core.pirn_opaque_value import PirnOpaqueValue  # local: avoids a cycle

        members = (
            get_args(annotation)
            if get_origin(annotation) in (Union, _types.UnionType)
            else (annotation,)
        )
        concrete = [m for m in members if m is not type(None)]
        if not concrete:
            return False
        return all(
            cls._is_knot_cls(m) or (isinstance(m, type) and issubclass(m, PirnOpaqueValue))
            for m in concrete
        )

    # ----------------------------------------------------------- properties

    @property
    def knot_id(self) -> str:
        """Stable string identifier for this knot within its tapestry."""
        return self._mutable_config.id

    @property
    def config(self) -> KnotConfig:
        """The ``KnotConfig`` supplied at construction."""
        return self._mutable_config

    @property
    def parents(self) -> Mapping[str, Knot]:
        """Read-only view of name → parent knot."""
        return dict(self._mutable_parents)

    @property
    def config_values(self) -> Mapping[str, Any]:
        """Read-only view of name → constant config value."""
        return dict(self._mutable_config_values)

    @property
    def input_names(self) -> tuple[str, ...]:
        """Names declared on process(), in declaration order."""
        return tuple(self._mutable_input_adapters.keys())

    # ------------------------------------------------------------- user-impl

    async def process(self, *args: Any, **kwargs: Any) -> Any:
        """Implement this.  This is the one method users override.

        Type annotations on parameters and return are honoured for
        validation when ``validate_io`` is True.
        The engine always calls process() with keyword arguments; *args
        is never passed and must not appear in overriding signatures —
        ``__init_subclass__`` refuses any override that declares it.

        The ``*args`` in *this* declaration is a typing device, not a call
        convention (PIR-833).  A concrete knot names its inputs and the engine
        binds them dynamically, so no override's parameter list is ever
        substitutable for this one; the gradual form makes a type checker skip
        the parameter half of the override check — and only that half, so a
        concrete knot whose ``process`` returns something its base cannot is
        still a hard error.  See ``_dynamic_process_signature``.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement process()")

    # -------------------------------------------------------------- runtime

    async def _prepare_inputs(
        self, parent_results: Mapping[str, Any]
    ) -> dict[str, Any] | Result[Any]:
        """Merge config values with resolved parent results, then fan-out or validate.

        Shared by ``Knot.__call__`` and ``SubTapestry.__call__``, which
        otherwise duplicated this exactly.

        Returns:
            The ``process()`` kwargs (a plain ``dict``) when input
            preparation succeeds ordinarily. When one or more inputs is a
            ``Map``/``ZipMap``/``DictMap`` marker, or ``validate_io``
            catches a bad input, returns an already-terminal ``Result``
            instead — the caller must return it immediately rather than
            call ``process()``.
        """
        config = self._mutable_config
        # Assemble the kwargs to process().  Parents override config in
        # the rare case both exist (shouldn't happen given our validation,
        # but be explicit).
        kwargs: dict[str, Any] = dict(self._mutable_config_values)
        kwargs.update(parent_results)

        # Fan-out path: one or more inputs are distribution markers.
        # Must happen before input validation — the collection type does not
        # match the declared per-element type.
        if self._mutable_mapped_inputs:
            try:
                outputs = await self._fan_out(kwargs)
            except BaseException as exc:
                if self._is_task_cancellation(exc):
                    raise
                return Err(record=ExceptionRecord.for_knot(config.id, exc))
            return Ok(value=outputs)

        if config.validate_io:
            try:
                kwargs = self._validate_inputs(kwargs)
            except ValidationError as exc:
                return Err(record=ExceptionRecord.for_knot(config.id, exc))

        return kwargs

    async def __call__(self, parent_results: Mapping[str, Any]) -> Result[Any]:
        """Framework entry point — invoked by the engine.

        ``parent_results`` is a mapping from this knot's input parameter
        name to the upstream value (or, under RECEIVE_ERRORS, the
        upstream Result).  Config values are merged in from
        ``self._mutable_config_values``.

        A ``process()`` that returns a ``Skipped`` is declaring that it
        deliberately produced no value -- a closed ``Gate``, a non-selected
        ``Branch`` arm, a denied approval.  The ``Skipped`` is returned as
        is, never wrapped in ``Ok`` and never checked against the return
        hint, so the engine records the knot as skipped and its children
        skip in turn (ADR agents-speaks-core, WS0).  ``Optional`` is the one
        exception: it keeps its ``Ok(Skipped)`` contract, so a downstream
        knot of an optional source still receives the ``Skipped`` as a value.
        """
        config = self._mutable_config
        prepared = await self._prepare_inputs(parent_results)
        if not isinstance(prepared, dict):
            return prepared
        kwargs = prepared

        try:
            result = await self.process(**kwargs)
        except BaseException as exc:
            if self._is_task_cancellation(exc):
                raise
            return Err(record=ExceptionRecord.for_knot(config.id, exc))

        if isinstance(result, Skipped):
            return result

        if config.validate_io and self._mutable_output_adapter is not None:
            try:
                result = self._mutable_output_adapter.validate_python(result)
            except ValidationError as exc:
                return Err(record=ExceptionRecord.for_knot(config.id, exc))

        return Ok(value=result)

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _is_task_cancellation(exc: BaseException) -> bool:
        """Whether *exc* is the running task being cancelled, not a knot's own raise.

        ``__call__`` turns every exception a knot raises into ``Err`` so the
        engine can record it.  ``asyncio.CancelledError`` is the one exception
        that is not the knot's to report: when the *task* is being cancelled
        -- the run was cancelled, or a ``KnotConfig.timeout`` expired -- the
        cancellation must reach the awaiting caller, or ``asyncio.wait_for``
        sees a knot that "finished" with an ``Err`` and never raises
        ``TimeoutError``, and a cancelled run returns a failed ``RunResult``
        instead of raising (PIR-849).

        A knot that raises ``CancelledError`` *itself*, with no cancellation
        pending on its task, is reporting an outcome like any other exception
        and still becomes ``Err``.  ``Task.cancelling()`` tells the two apart:
        it counts the cancel requests the task has received and not yet
        ``uncancel()``-led, so it is positive only for a real cancellation.
        A task-less context (a knot awaited outside asyncio's task machinery)
        cannot be cancelled and reports ``False``.

        Args:
            exc: The exception caught by a ``__call__`` boundary.

        Returns:
            ``True`` when *exc* must propagate, ``False`` when it is an ``Err``.
        """
        if not isinstance(exc, asyncio.CancelledError):
            return False
        try:
            task = asyncio.current_task()
        except RuntimeError:  # no running loop: nothing can be cancelling us
            return False
        return task is not None and task.cancelling() > 0

    @classmethod
    def _process_signature(cls) -> inspect.Signature:
        return inspect.signature(cls.process)

    @classmethod
    def _has_var_keyword(cls, sig: inspect.Signature) -> bool:
        return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())

    @classmethod
    def _declared_input_names(cls, sig: inspect.Signature) -> set[str]:
        names: set[str] = set()
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            if name in Knot._reserved_kwargs:
                # Authors should not name a process parameter `_config` or
                # `tapestry`; we forbid it at construction.
                raise TypeError(
                    f"{cls.__name__}.process: parameter name {name!r} "
                    "conflicts with a framework-reserved kwarg"
                )
            names.add(name)
        return names

    @classmethod
    def _process_hints(cls, sig: inspect.Signature) -> dict[str, Any]:
        """Resolve ``process()``'s type hints, keeping ``Annotated`` extras.

        We introspect ``cls.process`` (the unbound method) so that
        ``inspect.signature`` follows ``__wrapped__`` for ``@knot``-
        generated subclasses.  See Phase 1 commit history for the
        justification.

        ``include_extras=True`` keeps ``Annotated`` metadata on the hints.
        Without it :func:`get_type_hints` erases the annotation's extras, so
        ``Annotated[int, Field(gt=0)]`` reaches pydantic as a bare ``int`` and
        the constraint is silently dropped — validation that reads as declared
        but never runs.  Keeping the extras is what lets a knot state a value
        domain in its signature instead of re-checking it by hand in
        ``process``.
        """
        try:
            return get_type_hints(cls.process, include_extras=True)
        except Exception as exc:
            warnings.warn(
                f"{cls.__name__}.process: get_type_hints() failed ({exc!r}); "
                "input/output validation is disabled for this class regardless "
                "of KnotConfig.validate_io. This usually means a forward-"
                "referenced annotation cannot be resolved (e.g. a name only "
                "imported under TYPE_CHECKING).",
                stacklevel=3,
            )
            return {}

    @classmethod
    def _input_annotations(cls, sig: inspect.Signature, hints: Mapping[str, Any]) -> dict[str, Any]:
        """Name -> validation annotation for each named ``process()`` input.

        Shared by ``_build_adapters`` (what ``validate_io`` checks against)
        and ``input_json_schema`` (what a declaration advertises), so the two
        can never disagree.  For a ``Knot | T`` param the engine resolves the
        parent before calling ``process()``, so the runtime value is always
        ``T``, not ``Knot``: the annotation is ``T`` (``None``-preserving).
        An unannotated parameter maps to ``Any``.
        """
        coercible = cls._coercible_params
        annotations: dict[str, Any] = {}
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            ann = hints.get(name, param.annotation)
            if ann is inspect.Parameter.empty:
                annotations[name] = Any
                continue
            coerce_result = coercible.get(name)
            if coerce_result is not None:
                ann = coerce_result[1]  # adapter_type (non-Knot, None-preserving)
            annotations[name] = ann
        return annotations

    def _build_adapters(
        self,
        sig: inspect.Signature,
    ) -> tuple[dict[str, TypeAdapter], TypeAdapter | None]:
        """Build Pydantic ``TypeAdapter``s once at construction time.

        Input adapters come from ``_input_annotations`` -- one per annotated
        parameter -- or, for a schema-declared knot, from the declared
        schema's properties (``JsonSchemaTypeBuilder``).  The output adapter
        comes from the return hint either way.
        """
        hints = self._process_hints(sig)
        schema = type(self)._input_schema_override
        input_adapters: dict[str, TypeAdapter]
        if schema is not None:
            input_adapters = JsonSchemaTypeBuilder.input_adapters(schema)
        else:
            input_adapters = {
                name: TypeAdapter(ann)
                for name, ann in self._input_annotations(sig, hints).items()
                if ann is not Any or name in hints
            }

        ret = hints.get("return", sig.return_annotation)
        _is_knot_type = (
            ret is not inspect.Signature.empty
            and ret is not None
            and (ret is Knot or (isinstance(ret, type) and issubclass(ret, Knot)))
        )
        output_adapter = (
            None
            if ret is inspect.Signature.empty or ret is None or _is_knot_type
            else TypeAdapter(ret)
        )
        return input_adapters, output_adapter

    def _validate_inputs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name, value in kwargs.items():
            adapter = self._mutable_input_adapters.get(name)
            out[name] = adapter.validate_python(value) if adapter else value
        return out

    async def _fan_out(self, kwargs: dict[str, Any]) -> list[Any]:
        """Execute process() once per element, returning list[output].

        Raises MapTypeError if a collection has the wrong type.
        Propagates the first process() exception (cancels remaining tasks).
        """
        mapped = self._mutable_mapped_inputs
        sole_type = next(iter(mapped.values()))

        dict_keys: list[str] | None = None

        if sole_type is Map:
            (input_name,) = mapped.keys()
            collection = kwargs[input_name]
            if not isinstance(collection, (list, tuple)):
                raise MapTypeError(
                    f"{type(self).__name__}({self.knot_id!r}): Map requires a list "
                    f"or tuple, got {type(collection).__name__!r}. "
                    "To use a set, sort it into a list upstream."
                )
            coros = [self.process(**{**kwargs, input_name: element}) for element in collection]
            map_type = "map"
            element_count = len(collection)

        elif sole_type is ZipMap:
            names = list(mapped.keys())
            collections = [kwargs[n] for n in names]
            for n, coll in zip(names, collections, strict=True):
                if not isinstance(coll, (list, tuple)):
                    raise MapTypeError(
                        f"{type(self).__name__}({self.knot_id!r}): ZipMap input "
                        f"{n!r} requires a list or tuple, got {type(coll).__name__!r}"
                    )
            coros = [
                self.process(**{**kwargs, **dict(zip(names, elements, strict=False))})
                for elements in zip(*collections, strict=False)
            ]
            map_type = "zip_map"
            element_count = len(coros)

        else:  # DictMap
            (key_name, val_name) = mapped.keys()
            the_dict = kwargs[key_name]  # both inputs resolve to the same dict
            if not isinstance(the_dict, dict):
                raise MapTypeError(
                    f"{type(self).__name__}({self.knot_id!r}): DictMap requires a "
                    f"dict, got {type(the_dict).__name__!r}"
                )
            dict_keys = list(the_dict.keys())
            coros = [
                self.process(**{**kwargs, key_name: k, val_name: v}) for k, v in the_dict.items()
            ]
            map_type = "dict_map"
            element_count = len(the_dict)

        results = await asyncio.gather(*coros)
        fan_out_extra: dict[str, Any] = {"map_type": map_type, "element_count": element_count}
        if dict_keys is not None:
            fan_out_extra["dict_keys"] = dict_keys
        self._mutable_fan_out_extra = fan_out_extra
        return list(results)

    # ------------------------------------------------------------- mutation

    def __setattr__(self, name: str, value: Any) -> None:
        if self._frozen and not name.startswith("_mutable_"):
            raise AttributeError(
                f"Knot {type(self).__name__}({self.knot_id!r}) is immutable; cannot set {name!r}"
            )
        object.__setattr__(self, name, value)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.knot_id!r}>"

    def __hash__(self) -> int:
        # Identity-based hashing (knots are values, but their identity is
        # their id-within-tapestry; equality is identity).
        return id(self)

    def __eq__(self, other: object) -> bool:
        return self is other
