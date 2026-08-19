"""``PatternDescriptor`` — what the registry knows about one agentic pattern.

A descriptor is the registry's row: a public pattern *name*, the
:class:`~pirn.nodes.sub_tapestry.SubTapestry` subclass it maps to, and which
constructor parameter receives the builder's runtime seed. Everything else the
builder needs — which components a pattern requires, which knobs it accepts —
is **derived from the constructor signature** rather than restated here, so a
descriptor cannot drift out of step with the class it describes: adding a
required parameter to a pipeline immediately makes it a required component at
the builder, and renaming one immediately renames it.

That derivation is what lets one registry table cover every shipped pattern
instead of one bespoke ``_build_x`` method per pattern (PIR-730). The name is
the only thing stated by hand, deliberately: it is the public API surface and
must stay stable even when a class is renamed.

Patterns are named by a ``"module:ClassName"`` target and imported **on first
use**. This keeps the table declarative — a row is data, not 52 import
statements — and keeps the builder package free of import cycles with the
specialization tree it points at. It is *not* an install-size win today:
``pirn_agents/__init__.py`` calls ``Registry.fill_registry()``, which imports
every knot module in the package, so by the time anything reaches this table the
classes are already loaded. Lazy targets simply mean the registry does not add a
second reason to load them.

References:
    - :class:`pirn_agents.builder.agent_pattern_registry.AgentPatternRegistry`
"""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.builder.pattern_seed_kind import PatternSeedKind

#: Constructor parameters the registry supplies itself, never the caller.
_RESERVED_PARAMETERS = frozenset({"self", "_config"})

#: Import cache, keyed by target. Descriptors are frozen, so the cache lives here.
_RESOLVED: dict[str, type[SubTapestry]] = {}

#: Rows already checked against their class, keyed by ``(target, seed)``. Keyed
#: by the pair, not the target: two rows may share a class and differ in seed,
#: and the second must still be checked.
_VALIDATED: set[tuple[str, str]] = set()


@dataclass(frozen=True)
class PatternDescriptor:
    """One row of the pattern registry.

    Attributes
    ----------
    name:
        The public pattern name (e.g. ``"naive_rag"``). Stable API surface.
    target:
        ``"module:ClassName"`` locating the :class:`SubTapestry` subclass this
        name builds. Imported on first use.
    seed:
        The constructor parameter that receives the builder's ``.input(...)``.
        Conventionally the pipeline's first parameter — the subject it acts on.
    seed_kind:
        How that seed is coerced before binding.
    """

    name: str
    target: str
    seed: str
    seed_kind: PatternSeedKind = PatternSeedKind.VALUE

    def __post_init__(self) -> None:
        """Validate the row's own shape (not the class, which is not yet imported).

        Raises:
            TypeError: If ``name``, ``target`` or ``seed`` is not a string.
            ValueError: If any is empty, or ``target`` is not ``module:Class``.
        """
        for label, value in (("name", self.name), ("target", self.target), ("seed", self.seed)):
            if not isinstance(value, str):
                raise TypeError(
                    f"PatternDescriptor: {label} must be a str, got {type(value).__name__}"
                )
            if not value:
                raise ValueError(f"PatternDescriptor: {label} must be a non-empty string")
        if self.target.count(":") != 1:
            raise ValueError(
                f"PatternDescriptor {self.name!r}: target must be 'module:ClassName', "
                f"got {self.target!r}"
            )

    @property
    def module_name(self) -> str:
        """The module half of :attr:`target` (no import performed)."""
        return self.target.split(":", 1)[0]

    @property
    def class_name(self) -> str:
        """The class half of :attr:`target` (no import performed)."""
        return self.target.split(":", 1)[1]

    def knot_class(self) -> type[SubTapestry]:
        """Import and return the pattern's :class:`SubTapestry` subclass.

        The import is performed once per target and cached. Resolution is also
        where the row is checked against reality — that the class exists, is a
        :class:`SubTapestry`, and actually has the declared seed parameter.

        Raises:
            ImportError: If the module or class cannot be imported.
            TypeError: If the target is not a :class:`SubTapestry` subclass.
            ValueError: If :attr:`seed` is not one of its constructor parameters.
        """
        resolved = _RESOLVED.get(self.target)
        if resolved is None:
            module = importlib.import_module(self.module_name)
            # `vars(...)` rather than `getattr`: the class name is data, so the
            # lookup is a dict lookup, and the house rule reserves `getattr` for
            # cases with no plainer form (conventions/languages/python.md).
            candidate = vars(module).get(self.class_name)
            if candidate is None:
                raise ImportError(
                    f"PatternDescriptor {self.name!r}: {self.module_name!r} has no "
                    f"{self.class_name!r}"
                )
            if not (isinstance(candidate, type) and issubclass(candidate, SubTapestry)):
                raise TypeError(
                    f"PatternDescriptor {self.name!r}: {self.target} must be a SubTapestry "
                    f"subclass, got {candidate!r}"
                )
            _RESOLVED[self.target] = candidate
            resolved = candidate
        if (self.target, self.seed) not in _VALIDATED:
            if self.seed not in self.parameters():
                raise ValueError(
                    f"PatternDescriptor {self.name!r}: seed {self.seed!r} is not a constructor "
                    f"parameter of {self.class_name}; parameters are {sorted(self.parameters())!r}"
                )
            _VALIDATED.add((self.target, self.seed))
        return resolved

    def parameters(self) -> MappingProxyType[str, bool]:
        """Return the bindable constructor parameters, mapped to *has a default*.

        Excludes the parameters the registry owns (``self``, ``_config``) and
        any ``*args``/``**kwargs`` catch-all, which absorbs anything and so
        tells the builder nothing.
        """
        knot_class = _RESOLVED.get(self.target) or self.knot_class()
        signature = inspect.signature(knot_class.__init__)
        return MappingProxyType(
            {
                name: parameter.default is not inspect.Parameter.empty
                for name, parameter in signature.parameters.items()
                if name not in _RESERVED_PARAMETERS
                and parameter.kind is not inspect.Parameter.VAR_KEYWORD
                and parameter.kind is not inspect.Parameter.VAR_POSITIONAL
            }
        )

    def required_components(self) -> tuple[str, ...]:
        """Return the parameters a caller *must* supply, besides the seed.

        These are the constructor parameters with no default: the LLM provider,
        memory store, embedder, tool, specialist list, or whatever else this
        particular pattern cannot be built without.
        """
        return tuple(
            name
            for name, has_default in self.parameters().items()
            if not has_default and name != self.seed
        )

    def optional_parameters(self) -> tuple[str, ...]:
        """Return the parameters that have defaults — the pattern's knobs."""
        return tuple(name for name, has_default in self.parameters().items() if has_default)

    def accepts(self, parameter: str) -> bool:
        """Return whether this pattern's constructor takes ``parameter``."""
        return parameter in self.parameters()

    def describe(self) -> dict[str, Any]:
        """Return a plain, printable summary of this pattern's contract."""
        return {
            "name": self.name,
            "class": self.class_name,
            "module": self.module_name,
            "seed": self.seed,
            "seed_kind": self.seed_kind.value,
            "required": list(self.required_components()),
            "optional": list(self.optional_parameters()),
        }
