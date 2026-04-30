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
import inspect
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, get_type_hints

from pydantic import TypeAdapter, ValidationError

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.optional import Optional
from pirn.core.result import Result
from pirn.managers.exception_record import ExceptionRecord
from pirn.nodes.map_markers import DictMap, Map, MapTypeError, ZipMap

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
            if has_var_pos:
                raise TypeError(
                    f"{cls.__name__}.process may not declare *args; "
                    "pirn calls process() exclusively with keyword arguments"
                )
            if not has_var_kw:
                raise TypeError(
                    f"{cls.__name__}.process must include '**_: Any' to absorb "
                    "implicit dependencies; add it after all named parameters"
                )

    def __init__(self, **kwargs: Any) -> None:
        # Pull framework-reserved kwargs out first.
        config: KnotConfig = kwargs.pop("_config", None)  # type: ignore[assignment]  # None is narrowed to KnotConfig two lines below
        if config is None:
            raise TypeError(
                f"{type(self).__name__} requires _config=KnotConfig(id=...).  "
                "Pirn requires explicit knot ids; nothing is auto-generated."
            )
        if not isinstance(config, KnotConfig):
            raise TypeError(
                f"{type(self).__name__}: _config must be a KnotConfig instance, "
                f"got {type(config).__name__}"
            )

        explicit_tapestry: Tapestry | None = kwargs.pop("tapestry", None)

        # Detect and extract distribution markers (Map, ZipMap, DictMap) first,
        # before signature validation, so markers on declared inputs are treated
        # as Knot parents rather than non-Knot config errors.
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
        kwargs = resolved_kwargs

        # Validate marker consistency.
        if mapped_inputs:
            marker_types = set(mapped_inputs.values())
            if len(marker_types) > 1:
                raise TypeError(
                    f"{type(self).__name__}({config.id!r}): cannot mix "
                    "Map, ZipMap, and DictMap markers on the same knot"
                )
            sole_type = next(iter(marker_types))
            if sole_type is Map and len(mapped_inputs) > 1:
                raise TypeError(
                    f"{type(self).__name__}({config.id!r}): multiple Map-annotated "
                    "inputs would produce a cross-product; use ZipMap to zip "
                    "multiple collections element-wise"
                )
            if sole_type is DictMap and len(mapped_inputs) != 2:
                raise TypeError(
                    f"{type(self).__name__}({config.id!r}): DictMap requires exactly "
                    "two annotated inputs (key-receiver and value-receiver)"
                )
            if sole_type is DictMap:
                dict_sources = list(marker_sources.values())
                if dict_sources[0] is not dict_sources[1]:
                    raise TypeError(
                        f"{type(self).__name__}({config.id!r}): both DictMap inputs "
                        "must reference the same source knot"
                    )

        # Validate the remaining kwargs against process()'s signature.
        # follow_wrapped=True: for @knot classes, inspect the user's original
        # function so declared input names reflect its real parameter names.
        sig = self._process_signature()
        declared = self._declared_input_names(sig)
        accepts_implicit = self._has_var_keyword(sig)

        # Partition unknown kwargs: extra Knot-valued ones are implicit parents
        # (ordering dependencies whose output is not used directly); extra
        # non-Knot ones are always errors.
        unknown = set(kwargs) - declared - Knot._reserved_kwargs
        if unknown:
            if accepts_implicit:
                bad_config = {k for k in unknown if not isinstance(kwargs[k], Knot)}
                if bad_config:
                    raise TypeError(
                        f"{type(self).__name__}({config.id!r}): unknown non-Knot "
                        f"kwarg(s) {sorted(bad_config)!r}; only Knot parents may "
                        "be passed as implicit dependencies"
                    )
                # Remaining unknowns are all Knot-valued — accepted as implicit parents.
            else:
                raise TypeError(
                    f"{type(self).__name__}({config.id!r}): unknown kwarg(s) "
                    f"{sorted(unknown)!r}; declared inputs are {sorted(declared)!r}. "
                    "To wire implicit dependencies add '**_: Any' to process()"
                )

        # Reject missing explicit inputs.
        missing = declared - set(kwargs)
        if missing:
            raise TypeError(
                f"{type(self).__name__}({config.id!r}): missing required "
                f"input(s) {sorted(missing)!r}"
            )

        # Partition kwargs: explicit parents/configs (named in process) and
        # implicit parents (extra Knot kwargs absorbed by **_).
        parents: dict[str, Knot] = {}
        config_values: dict[str, Any] = {}
        for name, value in kwargs.items():
            if isinstance(value, Knot):
                parents[name] = value  # explicit and implicit parents both stored here
            else:
                config_values[name] = value

        # Build adapters for input/output validation now (one-time cost).
        input_adapters, output_adapter = self._build_adapters(sig)

        # Validate config values against their declared types eagerly —
        # they're constants, so we can check them at construction time.
        if config.validate_io:
            for name, value in config_values.items():
                adapter = input_adapters.get(name)
                if adapter is None:
                    continue
                try:
                    config_values[name] = adapter.validate_python(value)
                except ValidationError as exc:
                    raise TypeError(
                        f"{type(self).__name__}({config.id!r}).{name}: "
                        f"config value failed validation: {exc}"
                    ) from exc

        # Stash everything.  All `_mutable_` to bypass the freeze guard.
        self._mutable_config = config
        self._mutable_parents = parents
        self._mutable_config_values = config_values
        self._mutable_input_adapters = input_adapters
        self._mutable_output_adapter = output_adapter
        self._mutable_mapped_inputs: dict[str, type] = mapped_inputs

        # Self-register with the active tapestry (if any) or with the
        # explicitly passed one.  Done last so the knot is fully built
        # before the tapestry sees it.
        from pirn.tapestry import _CURRENT_TAPESTRY

        target_tapestry = explicit_tapestry or _CURRENT_TAPESTRY.get(None)
        if target_tapestry is not None:
            target_tapestry.register(self)

        self._frozen = True

    # ----------------------------------------------------------- properties

    @property
    def knot_id(self) -> str:
        return self._mutable_config.id

    @property
    def config(self) -> KnotConfig:
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

    @property
    def is_optional(self) -> bool:
        return isinstance(self, Optional)

    # ------------------------------------------------------------- user-impl

    async def process(self, **kwargs: Any) -> Any:
        """Implement this.  This is the one method users override.

        Type annotations on parameters and return are honoured for
        validation when ``validate_io`` is True.
        The engine always calls process() with keyword arguments; *args
        is never passed and must not appear in overriding signatures.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement process()")

    # -------------------------------------------------------------- runtime

    async def __call__(self, parent_results: Mapping[str, Any]) -> Result[Any]:
        """Framework entry point — invoked by the engine.

        ``parent_results`` is a mapping from this knot's input parameter
        name to the upstream value (or, under RECEIVE_ERRORS, the
        upstream Result).  Config values are merged in from
        ``self._mutable_config_values``.
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
                return Err(record=ExceptionRecord.for_knot(config.id, exc))
            return Ok(value=outputs)

        if config.validate_io:
            try:
                kwargs = self._validate_inputs(kwargs)
            except ValidationError as exc:
                return Err(record=ExceptionRecord.for_knot(config.id, exc))

        try:
            result = await self.process(**kwargs)
        except BaseException as exc:
            return Err(record=ExceptionRecord.for_knot(config.id, exc))

        if config.validate_io and self._mutable_output_adapter is not None:
            try:
                result = self._mutable_output_adapter.validate_python(result)
            except ValidationError as exc:
                return Err(record=ExceptionRecord.for_knot(config.id, exc))

        return Ok(value=result)

    # -------------------------------------------------------------- helpers

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

    def _build_adapters(
        self,
        sig: inspect.Signature,
    ) -> tuple[dict[str, TypeAdapter], TypeAdapter | None]:
        """Build Pydantic ``TypeAdapter``s once at construction time.

        We introspect ``type(self).process`` (the unbound method) so that
        ``inspect.signature`` follows ``__wrapped__`` for ``@knot``-
        generated subclasses.  See Phase 1 commit history for the
        justification.
        """
        process_fn = type(self).process
        try:
            hints = get_type_hints(process_fn)
        except Exception:
            hints = {}

        input_adapters: dict[str, TypeAdapter] = {}
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
                continue
            input_adapters[name] = TypeAdapter(ann)

        ret = hints.get("return", sig.return_annotation)
        output_adapter = None if ret is inspect.Signature.empty or ret is None else TypeAdapter(ret)
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

        elif sole_type is ZipMap:
            names = list(mapped.keys())
            collections = [kwargs[n] for n in names]
            for n, coll in zip(names, collections):
                if not isinstance(coll, (list, tuple)):
                    raise MapTypeError(
                        f"{type(self).__name__}({self.knot_id!r}): ZipMap input "
                        f"{n!r} requires a list or tuple, got {type(coll).__name__!r}"
                    )
            coros = [
                self.process(**{**kwargs, **dict(zip(names, elements))})
                for elements in zip(*collections)
            ]

        else:  # DictMap
            (key_name, val_name) = mapped.keys()
            the_dict = kwargs[key_name]  # both inputs resolve to the same dict
            if not isinstance(the_dict, dict):
                raise MapTypeError(
                    f"{type(self).__name__}({self.knot_id!r}): DictMap requires a "
                    f"dict, got {type(the_dict).__name__!r}"
                )
            coros = [
                self.process(**{**kwargs, key_name: k, val_name: v}) for k, v in the_dict.items()
            ]

        results = await asyncio.gather(*coros)
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
