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

from pydantic import BaseModel, ConfigDict, TypeAdapter

from pirn.core.config import KnotConfig
from pirn.core.knot import Knot

_UNSET = object()


class ParameterSpec(BaseModel):
    """Declarative description of a parameter.  Validated, serialisable."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    name: str
    type_: Any
    has_default: bool = False
    default: Any = None
    description: str | None = None


class Parameter(Knot):
    """A knot that produces a parameter's value at run start.

    Constructed with a name, type, and optional default.  Bound from
    ``RunRequest.parameters[name]`` (or default) before the run begins.
    """

    def __init__(
        self,
        name: str,
        type_: Any,
        *,
        default: Any = _UNSET,
        description: str | None = None,
        _config: KnotConfig | None = None,
        tapestry: Any = None,
    ) -> None:
        # Parameter has no `process` parameters, so the standard Knot
        # introspection would find nothing to validate.  We bypass most of
        # it and set up our own state.
        has_default = default is not _UNSET
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
        self._mutable_spec = spec
        self._mutable_value: Any = _UNSET

        # Self-register.
        from pirn.tapestry import _CURRENT_TAPESTRY

        target = tapestry or _CURRENT_TAPESTRY.get(None)
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

    async def process(self) -> Any:
        if self._mutable_value is not _UNSET:
            return self._mutable_value
        if self.has_default:
            return self.default
        raise RuntimeError(
            f"Parameter {self.name!r} has no value bound and no default"
        )
