"""``PromptBinding`` — the indirection that makes a built-in prompt tunable.

Every prompt literal shipped inside ``pirn_agents`` is declared as a
:class:`PromptBinding` class attribute instead of a bare ``str``. The binding
pairs the *registry name* an operator overrides against with the *built-in
default* that ships in the wheel, and :meth:`resolve` applies one documented
precedence at call time:

1. **Subclass override.** A public, documented ``ClassVar[str]`` that a subclass
   has changed away from the built-in wins outright — subclass customisation
   still beats deployment configuration, because the subclass author asked for
   specific text in code.
2. **Registered / loaded template.** Otherwise the catalog is consulted for
   ``(namespace, name[, version])``. That is where a prompt pack loaded from
   ``PIRN_AGENTS_PROMPT_PACKS`` — or registered by an application at start-up —
   takes effect.
3. **Built-in default.** With no override and nothing registered, the literal
   that shipped in the wheel is returned, byte for byte.

Because step 3 is a plain attribute read, converting a site costs nothing at
runtime when no pack is loaded and cannot change delivered text.

Prompts whose text *interleaves* runtime data — a target language, a tool name,
a rendered evidence block — are bound as whole ``{{ slot }}`` templates and read
through :meth:`render` instead. :meth:`render` runs :meth:`resolve` and then one
non-strict substitution pass, which is what makes the built-in default and a
loaded pack behave identically: :meth:`resolve` never fills slots (the catalog
is consulted with no variables, so a registered body comes back with its markers
still literal), and the single pass afterwards fills them for either source.
Binding only the static run around an interpolation was the alternative, and it
was rejected: several defaults would have been sentence fragments, and there is
nothing coherent for an operator to override.

``PromptBinding`` is a plain frozen dataclass rather than a
:class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`: it is class-level
configuration read inside ``process()``, never a value that crosses a knot IO
boundary, so it needs no pydantic core schema.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pirn_agents.prompt.prompt_catalog import PromptCatalog
from pirn_agents.prompt.prompt_template import PromptTemplate


@dataclass(frozen=True)
class PromptBinding:
    """A registry-backed binding for one built-in prompt literal.

    Attributes
    ----------
    name:
        The catalog name an operator overrides against. Built-ins use the
        owning module's dotted path under ``pirn_agents`` plus the attribute
        name with any leading underscore stripped — e.g.
        ``"specializations.chain_of_thought.chain_of_thought.system_prompt"``.
    default:
        The prompt text that ships in the wheel; returned when nothing is
        registered and no subclass has overridden the site.
    namespace:
        The catalog namespace to resolve in. Defaults to the built-in
        ``pirn_agents`` namespace so operator packs targeting shipped prompts
        cannot collide with an application's own templates.
    version:
        An exact version to pin to, or ``None`` (default) to take whichever
        version is newest in the catalog.
    """

    #: Version stamped on the throwaway :class:`PromptTemplate` :meth:`render`
    #: builds to perform its substitution pass. Never registered anywhere.
    _render_version: ClassVar[str] = "1.0.0"

    name: str
    default: str
    namespace: str = field(default_factory=PromptCatalog.builtin_namespace)
    version: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise TypeError("PromptBinding: name must be a non-empty str")
        if not isinstance(self.default, str):
            raise TypeError(
                f"PromptBinding: default must be a str, got {type(self.default).__name__}"
            )
        if not isinstance(self.namespace, str) or not self.namespace:
            raise TypeError("PromptBinding: namespace must be a non-empty str")
        if self.version is not None and (not isinstance(self.version, str) or not self.version):
            raise TypeError("PromptBinding: version must be a non-empty str or None")

    def resolve(
        self,
        declared: str | None = None,
        *,
        variables: Mapping[str, Any] | None = None,
        catalog: PromptCatalog | None = None,
    ) -> str:
        """Return the prompt text to send, applying the documented precedence.

        Args:
            declared: The value currently held by the public ``ClassVar[str]``
                this binding backs, for the handful of sites that document one
                as subclass-overridable. When it differs from :attr:`default` a
                subclass has customised it and that text is returned unchanged.
                Pass ``None`` (the default) for private, non-overridable sites.
            variables: Optional slot values for a registered template that
                declares ``{{ slots }}``. Built-in defaults are returned
                untouched, so a site with slots wants :meth:`render`, not this.
            catalog: The catalog to consult. Defaults to
                :meth:`PromptCatalog.shared`; pass an explicit catalog for tests
                or for embedding several tenants in one process.

        Returns:
            The prompt text, never ``None``.

        Notes:
            A subclass that re-declares the *same* text as the built-in is
            indistinguishable from not overriding at all, so a loaded pack still
            wins there. Overriding means changing the text.
        """
        if declared is not None and declared != self.default:
            return declared
        source = catalog if catalog is not None else PromptCatalog.shared()
        registered = source.resolve(
            self.name,
            namespace=self.namespace,
            version=self.version,
            variables=variables,
        )
        if registered is not None:
            return registered
        return self.default

    def render(
        self,
        variables: Mapping[str, Any] | None = None,
        declared: str | None = None,
        *,
        catalog: PromptCatalog | None = None,
    ) -> str:
        """Resolve the prompt text, then substitute ``{{ slots }}`` into it once.

        This is :meth:`resolve` for the sites whose prompt embeds runtime data.
        The binding holds the *whole* prompt as a template body, so an operator
        overrides one coherent unit and may move, repeat, or drop a slot; the
        call site just supplies the values.

        Both sources go through the same single pass. :meth:`resolve` consults
        the catalog with no variables, so a registered body arrives with its
        markers still literal, exactly like the built-in default — and one
        substitution afterwards fills either of them identically.

        Args:
            variables: Slot values keyed by name. Values are stringified by
                :class:`PromptTemplate`; pre-format anything whose text must be
                exact (``repr(...)``, ``json.dumps(...)``) at the call site.
            declared: As :meth:`resolve` — the current value of a public
                ``ClassVar[str]`` this binding backs, or ``None``.
            catalog: As :meth:`resolve`.

        Returns:
            The rendered prompt text, never ``None``.

        Notes:
            Substitution is non-strict and single-pass: a slot the caller did
            not supply stays literal rather than raising mid-turn inside an
            agent, and a substituted *value* containing ``{{ ... }}`` is inert
            because the pass never re-scans what it inserted.
        """
        return PromptTemplate(
            name=self.name,
            version=type(self)._render_version,
            template=self.resolve(declared, catalog=catalog),
        ).render(variables, strict=False)
