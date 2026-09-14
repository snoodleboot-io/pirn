"""``PromptCatalog`` — the lookup layer a :class:`PromptBinding` resolves against.

A catalog wraps a :class:`PromptTemplateRegistry` and adds the two things a
binding needs that a bare registry does not provide:

* **File loading.** :meth:`load_path` reads a *prompt pack* (see
  :class:`~pirn_agents.prompt.prompt_pack_loader.PromptPackLoader`) and registers
  everything in it, replacing any same-``(namespace, name, version)`` entry so a
  pack can be re-loaded idempotently.
* **A process-wide instance.** :meth:`shared` returns the catalog that every
  built-in prompt consults. The first call populates it from the
  ``PIRN_AGENTS_PROMPT_PACKS`` environment variable — an ``os.pathsep``-separated
  list of pack files — which is what makes built-in prompts tunable with **no
  code change at all**: point the variable at a YAML file and redeploy.

Applications that prefer explicit wiring over an environment variable can call
``PromptCatalog.shared().load_path(...)`` during start-up, or hand a private
catalog to :meth:`PromptBinding.resolve` for tests and multi-tenant embedding.

Nothing here imports a YAML backend: PyYAML is pulled in lazily by the loader
only when a ``.yaml``/``.yml`` pack is actually read.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

from pirn_agents.prompt.prompt_pack_loader import PromptPackLoader
from pirn_agents.prompt.prompt_template import PromptTemplate
from pirn_agents.prompt.prompt_template_registry import PromptTemplateRegistry


class PromptCatalog:
    """A loadable, process-shareable view over a :class:`PromptTemplateRegistry`."""

    #: The process-wide catalog, created lazily by :meth:`shared`.
    _shared: ClassVar[PromptCatalog | None] = None

    #: Namespace the built-in ``pirn_agents`` prompts register and resolve under.
    _builtin_namespace: ClassVar[str] = "pirn_agents"

    #: Environment variable naming the pack files loaded into :meth:`shared`.
    _packs_env_var: ClassVar[str] = "PIRN_AGENTS_PROMPT_PACKS"

    def __init__(self, registry: PromptTemplateRegistry | None = None) -> None:
        """Create a catalog over ``registry``, or over a fresh empty one.

        Args:
            registry: An existing registry to adopt. Defaults to a new, empty
                :class:`PromptTemplateRegistry`.

        Raises:
            TypeError: If ``registry`` is not a :class:`PromptTemplateRegistry`.
        """
        if registry is not None and not isinstance(registry, PromptTemplateRegistry):
            raise TypeError(
                "PromptCatalog: registry must be a PromptTemplateRegistry, "
                f"got {type(registry).__name__}"
            )
        self._registry: PromptTemplateRegistry = (
            registry if registry is not None else PromptTemplateRegistry()
        )

    @property
    def registry(self) -> PromptTemplateRegistry:
        """The underlying registry, for direct registration or introspection."""
        return self._registry

    @classmethod
    def builtin_namespace(cls) -> str:
        """Return the namespace the built-in ``pirn_agents`` prompts live in."""
        return cls._builtin_namespace

    @classmethod
    def packs_env_var(cls) -> str:
        """Return the environment variable :meth:`shared` reads pack paths from."""
        return cls._packs_env_var

    @classmethod
    def shared(cls) -> PromptCatalog:
        """Return the process-wide catalog, creating and loading it on first use.

        Creation reads :meth:`packs_env_var` and loads each pack path it names.
        A malformed or missing pack raises here rather than being ignored: a
        prompt override that silently did nothing would be worse than a loud
        start-up failure.
        """
        if cls._shared is None:
            catalog = cls()
            catalog.load_environment_packs()
            cls._shared = catalog
        return cls._shared

    @classmethod
    def reset_shared(cls) -> None:
        """Discard the process-wide catalog so the next :meth:`shared` rebuilds it."""
        cls._shared = None

    def load_environment_packs(self) -> tuple[str, ...]:
        """Load every pack named by :meth:`packs_env_var` into this catalog.

        Returns:
            The template names registered, in load order; empty when the
            variable is unset or blank.
        """
        raw = os.environ.get(type(self).packs_env_var(), "").strip()
        if not raw:
            return ()
        loaded: list[str] = []
        for entry in raw.split(os.pathsep):
            candidate = entry.strip()
            if candidate:
                loaded.extend(self.load_path(candidate))
        return tuple(loaded)

    def load_path(
        self, path: str | Path, *, allowed_root: str | Path | None = None
    ) -> tuple[str, ...]:
        """Load a prompt-pack file and register everything it declares.

        Args:
            path: The ``.json``/``.yaml``/``.yml`` pack to load.
            allowed_root: Optional containment root for an untrusted ``path``;
                see :meth:`PromptPackLoader.from_path`.

        Returns:
            The template names registered, in file order.

        Raises:
            ImportError: If a YAML pack is loaded without the ``yaml`` extra.
            ValueError: If the pack is malformed or the suffix is unsupported.
        """
        namespace, templates = PromptPackLoader.from_path(
            path,
            default_namespace=type(self).builtin_namespace(),
            allowed_root=allowed_root,
        )
        return self._register_all(namespace, templates)

    def load_mapping(self, data: Mapping[str, Any]) -> tuple[str, ...]:
        """Load an already-parsed prompt pack. See :meth:`load_path`."""
        namespace, templates = PromptPackLoader.from_mapping(
            data, default_namespace=type(self).builtin_namespace()
        )
        return self._register_all(namespace, templates)

    def load_json(self, text: str) -> tuple[str, ...]:
        """Load a JSON prompt pack from text. See :meth:`load_path`."""
        namespace, templates = PromptPackLoader.from_json(
            text, default_namespace=type(self).builtin_namespace()
        )
        return self._register_all(namespace, templates)

    def load_yaml(self, text: str) -> tuple[str, ...]:
        """Load a YAML prompt pack from text; needs the ``yaml`` extra.

        Raises:
            ImportError: If the ``yaml`` extra (PyYAML) is not installed.
        """
        namespace, templates = PromptPackLoader.from_yaml(
            text, default_namespace=type(self).builtin_namespace()
        )
        return self._register_all(namespace, templates)

    def resolve(
        self,
        name: str,
        *,
        namespace: str,
        version: str | None = None,
        variables: Mapping[str, Any] | None = None,
    ) -> str | None:
        """Render a registered template, or return ``None`` when none is registered.

        Rendering is non-strict: a slot the caller did not supply is left as
        literal ``{{ text }}`` rather than raising mid-turn inside an agent. An
        operator sees the stray marker in the prompt and fixes the pack; the
        agent does not crash.

        Args:
            name: The template name (a :class:`PromptBinding` name for built-ins).
            namespace: The namespace to look in.
            version: An exact version, or ``None`` for the newest registered.
            variables: Optional slot values.

        Returns:
            The rendered text, or ``None`` when nothing is registered.
        """
        template = self._registry.get(name, namespace=namespace, version=version)
        if template is None:
            return None
        return template.render(variables, strict=False)

    def _register_all(
        self, namespace: str, templates: tuple[PromptTemplate, ...]
    ) -> tuple[str, ...]:
        """Register ``templates`` under ``namespace``, replacing equal keys."""
        for template in templates:
            self._registry.unregister(template.name, namespace=namespace, version=template.version)
            self._registry.register(template, namespace=namespace)
        return tuple(template.name for template in templates)
