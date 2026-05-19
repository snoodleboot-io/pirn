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

from typing import Any

from pydantic import TypeAdapter

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter_spec import ParameterSpec
from pirn.core.sentinels._unset import _Unset
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
    """

    def __init__(
        self,
        name: str,
        type_: Any,
        *,
        default: Any = _Unset,
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
                supply a binding.  Omit (or pass ``_Unset``) to require the
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
        has_default = default is not _Unset
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
        # code clean.
        config = _config or KnotConfig(id=f"param:{name}")

        # Stash all _mutable_ state BEFORE the Knot.__init__ freeze.  We
        # don't call Knot.__init__ because its kwargs introspection would
        # refuse our parameters; instead we set the same fields it would.
        self._mutable_config = config
        self._mutable_parents = {}
        self._mutable_config_values = {}
        self._mutable_input_adapters = {}
        self._mutable_output_adapter = adapter
        self._mutable_mapped_inputs: dict[str, type] = {}
        self._mutable_spec = spec
        self._mutable_value: Any = _Unset

        # Self-register.
        from pirn.tapestry import _current_tapestry

        target = tapestry or _current_tapestry.get(None)
        if target is not None:
            target.register(self)

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
        return self._mutable_output_adapter.validate_python(supplied)

    def bind_value(self, value: Any) -> None:
        """Set the bound value (engine internal).

        ``_mutable_value`` starts with ``_mutable_`` so the Knot freeze
        guard permits this normal assignment without bypass tricks.
        """
        self._mutable_value = value

    async def process(self, **_: Any) -> Any:
        """Return the bound parameter value, falling back to the declared default.

        Returns:
            The bound parameter value, or the declared default if no value was bound.

        Raises:
            UnboundParameterError: If no value is bound and no default is declared.
        """
        if self._mutable_value is not _Unset:
            return self._mutable_value
        if self.has_default:
            return self.default
        raise UnboundParameterError(f"Parameter {self.name!r} has no value bound and no default")
