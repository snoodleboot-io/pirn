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
instead of one bespoke ``_build_x`` method per pattern (PIR-730). The name and
the seed/kind are the only things stated by hand, deliberately: the name is
the public API surface and must stay stable even when a class is renamed, and
the seed is a choice about which parameter varies per run (PIR-870) — this is
the "companion metadata" the class itself cannot tell us.

**Class resolution is a bare class name looked up in the sweet_tea
``Registry``, not a hand-typed ``"module:ClassName"`` string (PIR-870).**
``pirn_agents/__init__.py`` calls ``Registry.fill_registry()`` before this
table is ever consulted, which imports every knot module in the package and
registers each class it finds under its own lowercased name
(``library="pirn"``). A descriptor's :attr:`class_name` is just that
registration key with its original casing — the *module path* is derived
by asking the resolved class for its own ``__module__`` rather than being
restated by hand per row. Before this, ``target`` duplicated exactly what
``fill_registry`` already knew (52 hand-typed module paths that could drift
if a file moved), and doubled the cost of a rename: the class *and* the row
both had to change. Resolution is still performed once per class and cached,
and still on first use — nothing about the row's laziness or the freedom from
import cycles this package needs from its own ``specializations/`` tree
changes.

References:
    - :class:`pirn_agents.builder.agent_pattern_registry.AgentPatternRegistry`
    - :class:`sweet_tea.registry.Registry`
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, ClassVar

from pirn.nodes.sub_tapestry import SubTapestry
from sweet_tea.registry import Registry

from pirn_agents.builder.pattern_seed_kind import PatternSeedKind


@dataclass(frozen=True)
class PatternDescriptor:
    """One row of the pattern registry.

    Attributes
    ----------
    name:
        The public pattern name (e.g. ``"naive_rag"``). Stable API surface.
    class_name:
        The :class:`SubTapestry` subclass's own name (e.g.
        ``"NaiveRAGPipeline"``), resolved through the sweet_tea ``Registry``
        rather than a hand-typed module path. Imported on first use.
    seed:
        The constructor parameter that receives the builder's ``.input(...)``.
        Conventionally the pipeline's first parameter — the subject it acts on.
    seed_kind:
        How that seed is coerced before binding.
    """

    #: The ``library`` every pattern class is auto-registered under by
    #: ``Registry.fill_registry(module="pirn_agents", library="pirn")``
    #: (``pirn_agents/__init__.py``). Scopes a bare-class-name lookup to this
    #: package's own classes so it can never resolve to another library's
    #: same-named class sharing the one process-wide sweet_tea registry.
    _auto_fill_library: ClassVar[str] = "pirn"

    #: ``Registry.fill_registry`` calls ``Registry.register`` with no ``label``,
    #: so every auto-discovered class carries the empty label. Distinguishes an
    #: auto-discovered entry from one ``AgentPatternRegistry.register_with_core_registry``
    #: adds later under ``label="pattern"`` for the *pattern name* (not the class
    #: name), which would otherwise also match a lookup keyed by class name for a
    #: pattern whose name happens to lowercase to its own class's key.
    _auto_fill_label: ClassVar[str] = ""

    #: Constructor parameters the registry supplies itself, never the caller.
    #: ``ClassVar`` excludes it from the dataclass's own fields.
    _reserved_parameters: ClassVar[frozenset[str]] = frozenset({"self", "_config"})

    #: Import cache, keyed by class_name. Descriptors are frozen, so the cache
    #: lives on the class instead of an instance.
    _resolved: ClassVar[dict[str, type[SubTapestry]]] = {}

    #: Rows already checked against their class, keyed by ``(class_name, seed)``.
    #: Keyed by the pair, not the class name: two rows may share a class and
    #: differ in seed, and the second must still be checked.
    _validated: ClassVar[set[tuple[str, str]]] = set()

    name: str
    class_name: str
    seed: str
    seed_kind: PatternSeedKind = PatternSeedKind.VALUE

    def __post_init__(self) -> None:
        """Validate the row's own shape (not the class, which is not yet resolved).

        Raises:
            TypeError: If ``name``, ``class_name`` or ``seed`` is not a string.
            ValueError: If any is empty.
        """
        for label, value in (
            ("name", self.name),
            ("class_name", self.class_name),
            ("seed", self.seed),
        ):
            if not isinstance(value, str):
                raise TypeError(
                    f"PatternDescriptor: {label} must be a str, got {type(value).__name__}"
                )
            if not value:
                raise ValueError(f"PatternDescriptor: {label} must be a non-empty string")

    def knot_class(self) -> type[SubTapestry]:
        """Resolve and return the pattern's :class:`SubTapestry` subclass.

        Looked up in the sweet_tea ``Registry`` by :attr:`class_name` — see the
        module docstring — rather than imported from a stored module path.
        Resolution is performed once per class name and cached. It is also
        where the row is checked against reality — that the class exists
        uniquely, is a :class:`SubTapestry`, and actually has the declared
        seed parameter.

        Raises:
            ImportError: If no class named :attr:`class_name` is registered
                under the ``pirn`` library, or more than one is (which would
                mean the registry-uniqueness gate this codebase enforces
                elsewhere has itself been violated).
            TypeError: If the resolved class is not a :class:`SubTapestry`
                subclass.
            ValueError: If :attr:`seed` is not one of its constructor
                parameters.
        """
        resolved = type(self)._resolved.get(self.class_name)
        if resolved is None:
            candidate = self._resolve_from_registry()
            if not (isinstance(candidate, type) and issubclass(candidate, SubTapestry)):
                raise TypeError(
                    f"PatternDescriptor {self.name!r}: {self.class_name} must be a "
                    f"SubTapestry subclass, got {candidate!r}"
                )
            type(self)._resolved[self.class_name] = candidate
            resolved = candidate
        if (self.class_name, self.seed) not in type(self)._validated:
            if self.seed not in self.parameters():
                raise ValueError(
                    f"PatternDescriptor {self.name!r}: seed {self.seed!r} is not a constructor "
                    f"parameter of {self.class_name}; parameters are {sorted(self.parameters())!r}"
                )
            type(self)._validated.add((self.class_name, self.seed))
        return resolved

    def _resolve_from_registry(self) -> type:
        """Return the unique ``pirn``-library class named :attr:`class_name`.

        Raises:
            ImportError: If zero, or more than one, class of that name is
                registered under the ``pirn`` library with the auto-fill
                label — the latter can only mean this codebase's own
                registry-uniqueness invariant was violated elsewhere.
        """
        matches = [
            entry.class_def
            for entry in Registry.entries()
            if entry.key == self.class_name.lower()
            and entry.library == self._auto_fill_library
            and entry.label == self._auto_fill_label
        ]
        if not matches:
            raise ImportError(
                f"PatternDescriptor {self.name!r}: no class named {self.class_name!r} is "
                f"registered under the {self._auto_fill_library!r} library; is it defined under "
                "pirn_agents and has Registry.fill_registry() run yet?"
            )
        if len(matches) > 1:
            raise ImportError(
                f"PatternDescriptor {self.name!r}: {len(matches)} classes named "
                f"{self.class_name!r} are registered under the {self._auto_fill_library!r} "
                "library; class names must be globally unique"
            )
        return matches[0]

    def parameters(self) -> MappingProxyType[str, bool]:
        """Return the bindable constructor parameters, mapped to *has a default*.

        Excludes the parameters the registry owns (``self``, ``_config``) and
        any ``*args``/``**kwargs`` catch-all, which absorbs anything and so
        tells the builder nothing.
        """
        knot_class = type(self)._resolved.get(self.class_name) or self.knot_class()
        signature = inspect.signature(knot_class.__init__)
        return MappingProxyType(
            {
                name: parameter.default is not inspect.Parameter.empty
                for name, parameter in signature.parameters.items()
                if name not in type(self)._reserved_parameters
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
        """Return a plain, printable summary of this pattern's contract.

        Resolves the class (to read its ``required``/``optional`` parameters
        and its true ``module``), unlike the purely name-shaped accessors.
        """
        return {
            "name": self.name,
            "class": self.class_name,
            "module": self.knot_class().__module__,
            "seed": self.seed,
            "seed_kind": self.seed_kind.value,
            "required": list(self.required_components()),
            "optional": list(self.optional_parameters()),
        }
