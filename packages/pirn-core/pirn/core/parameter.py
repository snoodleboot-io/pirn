"""Parameter — a graph-level input.

A ``Parameter`` is a knot with no parents whose value is supplied at run
start (via ``RunRequest.parameters``) or from a default.  It is the
canonical way to inject data into a pipeline from outside.

Parameters use the new constructor convention but bypass the parent/config
introspection because their semantics are entirely framework-managed:
they take a ``name`` and ``type_`` at construction, and produce that
type's value at run time.
"""

from __future__ import annotations

import copy
from typing import Any

from pydantic import TypeAdapter, ValidationError

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter_spec import ParameterSpec
from pirn.core.sentinels.unset import Unset
from pirn.exceptions.unbound_parameter_error import UnboundParameterError


class Parameter(Knot):
    """A knot that produces a parameter's value at run start.

    ``Parameter`` is a source knot — it has no parents and is the canonical
    entry point for injecting caller-supplied data into a pipeline.  Values
    are bound from ``RunRequest.parameters[name]`` before the scheduler
    dispatches any work; a declared default is used when the caller omits the
    binding.

    Unlike ordinary knots, ``Parameter`` bypasses the standard Knot
    constructor introspection because its ``process()`` signature is entirely
    framework-managed.  Construction is therefore direct: state is populated
    without calling ``Knot.__init__``.

    Attributes:
        name: The parameter name.  Must match the key used in
            ``RunRequest.parameters``.
        type_: The expected Python type.  Values are validated with a Pydantic
            ``TypeAdapter`` at bind time.
        has_default: ``True`` when a default was supplied at construction.
        default: The fallback value when no binding is present.  Raises
            ``AttributeError`` when accessed on a parameter with no default.
        spec: The ``ParameterSpec`` describing this parameter for schema
            export and documentation.

    Algorithm:
        1. Construction — a ``TypeAdapter`` for ``type_`` is built once and
           stored as the knot's output adapter; no parent/config
           introspection runs, since ``Parameter`` has no declared inputs.
        2. Binding (per run) — before the engine dispatches any work,
           ``Engine._bind_parameters`` looks up ``RunRequest.parameters[name]``.
           If present, the value is validated via :meth:`bind`. If absent and
           a default was declared, the default is used unvalidated (it was
           supplied by the pipeline author, not an external caller). If
           neither is available, resolution defers to ``process()``.
        3. Run-scoped copy — the bound value is written onto a *copy* of this
           ``Parameter`` (:meth:`bound_copy`), never onto the shared graph
           knot, so concurrent runs sharing one ``Tapestry`` do not overwrite
           each other's bindings (PIR-802).
        4. Resolution — ``process()`` returns the bound value if one was set
           on this instance, else the declared default, else raises
           ``UnboundParameterError``.
    """

    def __init__(
        self,
        name: str,
        type_: Any,
        *,
        default: Any = Unset,
        description: str | None = None,
        _config: KnotConfig | None = None,
        tapestry: Any = None,
    ) -> None:
        """Construct a ``Parameter`` knot.

        Args:
            name: Identifier for this parameter.  Must be unique within the
                tapestry and must match the key callers use in
                ``RunRequest.parameters``.
            type_: The Python type the bound value must conform to.  Any type
                accepted by ``pydantic.TypeAdapter`` is valid.
            default: Optional fallback value used when the caller does not
                supply a binding.  Omit (or pass ``Unset``) to require the
                caller to always supply a value.
            description: Human-readable description surfaced in schema exports
                and visualisations.
            _config: Framework configuration override.  When ``None``, a
                stable default ``KnotConfig`` keyed as ``param:<name>`` is
                created automatically.
            tapestry: Explicit tapestry to register with.  When ``None``, the
                current context-var tapestry is used (standard pipeline
                construction idiom).
        """
        # Parameter has no `process` parameters, so the standard Knot
        # introspection would find nothing to validate.  We bypass most of
        # it and set up our own state.
        has_default = default is not Unset
        spec = ParameterSpec(
            name=name,
            type_=type_,
            has_default=has_default,
            default=default if has_default else None,
            description=description,
        )
        adapter = TypeAdapter(type_)

        # Default _config: id derived from name when not given.  Parameters
        # are common enough that we provide a stable default to keep user
        # code clean.  ``_bootstrap`` refuses anything that is not a
        # ``KnotConfig``, so a root gets the same check ``Knot.__init__`` does.
        config = _config or KnotConfig(id=f"param:{name}")

        # A declared default is the pipeline author's own value, so it is not
        # validated per run -- but it is validated once, here, against the type
        # this parameter declares.  A default that does not match its declared
        # type is a build-time mistake, and it used to surface only when a run
        # that omitted the binding reached the parameter (PIR-873).
        if has_default and config.validate_io:
            try:
                adapter.validate_python(default)
            except ValidationError as exc:
                raise TypeError(
                    f"Parameter({name!r}): default {default!r} does not match "
                    f"the declared type {type_!r}: {exc}"
                ) from exc

        # Stash all _mutable_ state BEFORE the Knot.__init__ freeze.  We
        # don't call Knot.__init__ because its kwargs introspection would
        # refuse our parameters; instead we go through the shared
        # _bootstrap() helper that stashes the same fields and self-registers.
        self._mutable_spec = spec
        self._mutable_value: Any = Unset
        self._bootstrap(config=config, parents={}, output_adapter=adapter, tapestry=tapestry)

        self._frozen = True

    # ---------------------------------------------------------- properties

    @property
    def spec(self) -> ParameterSpec:
        return self._mutable_spec

    @property
    def name(self) -> str:
        return self._mutable_spec.name

    @property
    def type_(self) -> Any:
        return self._mutable_spec.type_

    @property
    def has_default(self) -> bool:
        return self._mutable_spec.has_default

    @property
    def default(self) -> Any:
        if not self._mutable_spec.has_default:
            raise AttributeError(f"Parameter {self.name!r} has no default")
        return self._mutable_spec.default

    # ----------------------------------------------------------- run-start

    def bind(self, supplied: Any) -> Any:
        """Validate a supplied value; called by the engine before the run."""
        adapter = self._mutable_output_adapter
        assert adapter is not None, "Parameter always constructs its output_adapter"
        return adapter.validate_python(supplied)

    def bound_copy(self, value: Any) -> Parameter:
        """Return a run-scoped copy of this parameter carrying ``value``.

        The engine binds parameters per run rather than onto the shared
        graph.  A ``Tapestry`` is routinely built once at startup and used to
        serve many requests; writing the value onto the shared instance let
        concurrent runs overwrite one another, so every run computed with
        whichever request bound last while still reporting its own run id --
        wrong answers with no error and a plausible lineage record (PIR-802).

        The copy keeps this parameter's ``knot_id``, spec and validation
        adapter, so the engine's id-keyed bookkeeping (shed, results,
        lineage) is unaffected.  It deliberately does not register with a
        tapestry: it belongs to one run, not to the graph.  Because the value
        travels on the returned knot rather than in ambient context, a
        dispatcher that serializes the knot to another thread, process or
        machine still carries the binding with it.

        Args:
            value: The already-validated value this run should see.

        Returns:
            A new ``Parameter`` bound to ``value``, leaving ``self`` untouched.
        """
        clone = copy.copy(self)
        clone._mutable_value = value
        return clone

    async def process(self, **_: Any) -> Any:
        """Return the bound parameter value, falling back to the declared default.

        Returns:
            The bound parameter value, or the declared default if no value was bound.

        Raises:
            UnboundParameterError: If no value is bound and no default is declared.
        """
        if self._mutable_value is not Unset:
            return self._mutable_value
        if self.has_default:
            return self.default
        raise UnboundParameterError(f"Parameter {self.name!r} has no value bound and no default")
