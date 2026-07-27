"""``PromptPackLoader`` — parse a *prompt pack* file into :class:`PromptTemplate` values.

A prompt pack is the operator-facing file format behind
:class:`~pirn_agents.prompt.prompt_binding.PromptBinding`: dropping a pack next
to a deployment retunes any built-in prompt without touching Python. The format
is deliberately small::

    namespace: pirn_agents            # optional; falls back to the caller's default
    templates:
      specializations.chain_of_thought.system_prompt: |
        Think step-by-step, and answer in French.
      control.reflection_check.reflection_prompt:
        version: "2.0.0"
        description: Terser reflection gate.
        template: "Answer yes or no."
        partials:
          preamble: "You are terse."

Each entry under ``templates`` is either a bare string (the template body, at
the default version) or a mapping with an explicit ``template`` plus optional
``version`` / ``description`` / ``partials``.

JSON support uses only the standard library. YAML support is lazily provided by
the optional ``yaml`` extra (PyYAML): importing this module — and importing
``pirn_agents`` as a whole — never pulls in PyYAML. The backend is imported the
first time :meth:`from_yaml` is called, via the shared :func:`_require` helper,
which raises a friendly ``pip install "pirn-agents[yaml]"`` message when absent.
This mirrors :class:`~pirn_agents.builder.agent_spec_loader.AgentSpecLoader`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

from pirn_agents._internal._require import _require
from pirn_agents.prompt.prompt_template import PromptTemplate
from pirn_agents.tools.filesystem._path_guard import PathGuard


class PromptPackLoader:
    """Parser turning prompt-pack text into ``(namespace, templates)`` pairs."""

    #: Version assigned to a pack entry that does not declare one.
    _default_version: ClassVar[str] = "1.0.0"

    @classmethod
    def default_version(cls) -> str:
        """Return the version assigned to pack entries that omit ``version``."""
        return cls._default_version

    @classmethod
    def from_mapping(
        cls, data: Mapping[str, Any], *, default_namespace: str
    ) -> tuple[str, tuple[PromptTemplate, ...]]:
        """Build ``(namespace, templates)`` from an already-parsed pack mapping.

        Args:
            data: The parsed pack: an optional ``namespace`` plus a ``templates``
                mapping of template name to body-or-spec.
            default_namespace: Namespace used when the pack omits ``namespace``.

        Returns:
            The resolved namespace and the templates it declares, in file order.

        Raises:
            TypeError: If ``data`` is not a mapping or an entry has the wrong shape.
            ValueError: If ``namespace``/``templates`` are missing or malformed.
        """
        if not isinstance(data, Mapping):
            raise TypeError(f"PromptPackLoader: pack must be a mapping, got {type(data).__name__}")
        namespace = data.get("namespace", default_namespace)
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("PromptPackLoader: 'namespace' must be a non-empty string")
        raw_templates = data.get("templates")
        if raw_templates is None:
            raise ValueError("PromptPackLoader: pack must declare a 'templates' mapping")
        if not isinstance(raw_templates, Mapping):
            raise TypeError(
                "PromptPackLoader: 'templates' must be a mapping of name -> body, "
                f"got {type(raw_templates).__name__}"
            )
        templates = tuple(cls._build(name, body) for name, body in raw_templates.items())
        return namespace, templates

    @classmethod
    def from_json(
        cls, text: str, *, default_namespace: str
    ) -> tuple[str, tuple[PromptTemplate, ...]]:
        """Parse a JSON prompt pack.

        Raises:
            TypeError: If the top-level JSON value is not an object.
            ValueError: If ``text`` is not valid JSON or the pack is invalid.
        """
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"PromptPackLoader.from_json: invalid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise TypeError(
                "PromptPackLoader.from_json: top-level JSON must be an object, "
                f"got {type(parsed).__name__}"
            )
        return cls.from_mapping(parsed, default_namespace=default_namespace)

    @classmethod
    def from_yaml(
        cls, text: str, *, default_namespace: str
    ) -> tuple[str, tuple[PromptTemplate, ...]]:
        """Parse a YAML prompt pack.

        Raises:
            ImportError: If the ``yaml`` extra (PyYAML) is not installed.
            TypeError: If the top-level YAML value is not a mapping.
            ValueError: If ``text`` is not valid YAML or the pack is invalid.
        """
        yaml = _require("yaml", "yaml")
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f"PromptPackLoader.from_yaml: invalid YAML: {exc}") from exc
        if not isinstance(parsed, dict):
            raise TypeError(
                "PromptPackLoader.from_yaml: top-level YAML must be a mapping, "
                f"got {type(parsed).__name__}"
            )
        return cls.from_mapping(parsed, default_namespace=default_namespace)

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        *,
        default_namespace: str,
        allowed_root: str | Path | None = None,
    ) -> tuple[str, tuple[PromptTemplate, ...]]:
        """Load a prompt pack from a file, dispatching on its suffix.

        ``.json`` uses the JSON parser; ``.yaml``/``.yml`` use the YAML parser.

        Trust boundary. By default ``path`` is read as given — an operator-trusted
        file location, exactly like any other config file. When ``path`` may come
        from an untrusted or multi-tenant source, pass ``allowed_root``: ``path``
        is then treated as *relative to* that root and vetted by
        :class:`~pirn_agents.tools.filesystem._path_guard.PathGuard`, which
        rejects absolute paths, ``..`` traversal, symlink stepping-stones, and any
        escape from the root, before the file is read.

        Args:
            path: The pack file to load.
            default_namespace: Namespace used when the pack omits ``namespace``.
            allowed_root: Optional containment root for untrusted ``path`` values.

        Returns:
            The resolved namespace and the templates the pack declares.

        Raises:
            ImportError: If a YAML pack is loaded without the ``yaml`` extra.
            ValueError: If the suffix is not one of ``.json``, ``.yaml``, ``.yml``,
                or (when ``allowed_root`` is set) if ``path`` escapes the root.
        """
        if allowed_root is not None:
            file_path = PathGuard(root=str(allowed_root)).resolve(str(path), must_exist=True)
        else:
            file_path = Path(path)
        text = file_path.read_text(encoding="utf-8")
        suffix = file_path.suffix.lower()
        if suffix == ".json":
            return cls.from_json(text, default_namespace=default_namespace)
        if suffix in (".yaml", ".yml"):
            return cls.from_yaml(text, default_namespace=default_namespace)
        raise ValueError(
            f"PromptPackLoader.from_path: unsupported suffix {suffix!r}; "
            "expected .json, .yaml, or .yml"
        )

    @classmethod
    def _build(cls, name: object, body: object) -> PromptTemplate:
        """Turn one ``templates`` entry into a :class:`PromptTemplate`."""
        if not isinstance(name, str) or not name:
            raise ValueError(
                f"PromptPackLoader: template names must be non-empty strings: {name!r}"
            )
        if isinstance(body, str):
            return PromptTemplate(name=name, version=cls._default_version, template=body)
        if not isinstance(body, Mapping):
            raise TypeError(
                f"PromptPackLoader: template {name!r} must be a string body or a mapping, "
                f"got {type(body).__name__}"
            )
        template = body.get("template")
        if not isinstance(template, str):
            raise ValueError(
                f"PromptPackLoader: template {name!r} must declare a string 'template'"
            )
        version = body.get("version", cls._default_version)
        if not isinstance(version, str) or not version:
            raise ValueError(f"PromptPackLoader: template {name!r} has a non-string 'version'")
        description = body.get("description", "")
        if not isinstance(description, str):
            raise ValueError(f"PromptPackLoader: template {name!r} has a non-string 'description'")
        raw_partials = body.get("partials", {})
        if not isinstance(raw_partials, Mapping):
            raise TypeError(
                f"PromptPackLoader: template {name!r} has non-mapping 'partials', "
                f"got {type(raw_partials).__name__}"
            )
        return PromptTemplate(
            name=name,
            version=version,
            template=template,
            partials=dict(raw_partials),
            description=description,
        )
