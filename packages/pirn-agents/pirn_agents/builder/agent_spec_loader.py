"""``AgentSpecLoader`` — parse/serialise :class:`AgentSpec` from JSON and YAML.

JSON support uses only the standard library. YAML support is lazily provided
by the optional ``yaml`` extra (PyYAML); importing this module — and importing
``pirn_agents`` as a whole — never pulls in PyYAML, so the base install stays
backend-free. The YAML backend is imported the first time :meth:`from_yaml` or
:meth:`to_yaml` is called, via the shared :func:`_require` helper, which raises
a friendly ``pip install "pirn-agents[yaml]"`` message when it is absent.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pirn_agents._internal._require import _require
from pirn_agents.builder.agent_spec import AgentSpec
from pirn_agents.tools.filesystem._path_guard import PathGuard


class AgentSpecLoader:
    """Loader/serialiser bridging :class:`AgentSpec` and JSON/YAML text."""

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> AgentSpec:
        """Build an :class:`AgentSpec` from an already-parsed mapping."""
        return AgentSpec.from_dict(data)

    @classmethod
    def from_json(cls, text: str) -> AgentSpec:
        """Parse a JSON object string into a validated :class:`AgentSpec`.

        Raises:
            TypeError: If the top-level JSON value is not an object.
            ValueError: If ``text`` is not valid JSON or the object is invalid.
        """
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"AgentSpecLoader.from_json: invalid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise TypeError(
                f"AgentSpecLoader.from_json: top-level JSON must be an object, "
                f"got {type(parsed).__name__}"
            )
        return AgentSpec.from_dict(parsed)

    @classmethod
    def from_yaml(cls, text: str) -> AgentSpec:
        """Parse a YAML mapping string into a validated :class:`AgentSpec`.

        Raises:
            ImportError: If the ``yaml`` extra (PyYAML) is not installed.
            TypeError: If the top-level YAML value is not a mapping.
            ValueError: If ``text`` is not valid YAML or the mapping is invalid.
        """
        yaml = _require("yaml", "yaml")
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f"AgentSpecLoader.from_yaml: invalid YAML: {exc}") from exc
        if not isinstance(parsed, dict):
            raise TypeError(
                f"AgentSpecLoader.from_yaml: top-level YAML must be a mapping, "
                f"got {type(parsed).__name__}"
            )
        return AgentSpec.from_dict(parsed)

    @classmethod
    def from_path(cls, path: str | Path, *, allowed_root: str | Path | None = None) -> AgentSpec:
        """Load an :class:`AgentSpec` from a file, dispatching on its suffix.

        ``.json`` uses the JSON parser; ``.yaml``/``.yml`` use the YAML parser.

        Trust boundary. By default ``path`` is read as given — an
        operator-trusted file location, exactly like opening any other config
        file, and the caller owns whatever it points at. When ``path`` may come
        from an untrusted or multi-tenant source (templated from a request,
        derived from user config), pass ``allowed_root``: ``path`` is then
        treated as *relative to* that root and vetted by
        :class:`~pirn_agents.tools.filesystem._path_guard.PathGuard` — which
        rejects absolute paths, ``..`` traversal, symlink stepping-stones, and
        any escape from the root — before the file is read. This reuses the F-series
        path guard rather than re-deriving a containment check here.

        Args:
            path: The spec file to load. Absolute or operator-relative when
                ``allowed_root`` is ``None``; a root-relative path otherwise.
            allowed_root: Optional containment root. When set, ``path`` must
                resolve to an existing file inside it or a :class:`ValueError`
                is raised.

        Raises:
            ValueError: If the suffix is not one of ``.json``, ``.yaml``, ``.yml``,
                or (when ``allowed_root`` is set) if ``path`` escapes the root,
                traverses a symlink, is absolute, or does not exist.
        """
        if allowed_root is not None:
            file_path = PathGuard(root=str(allowed_root)).resolve(str(path), must_exist=True)
        else:
            file_path = Path(path)
        text = file_path.read_text(encoding="utf-8")
        suffix = file_path.suffix.lower()
        if suffix == ".json":
            return cls.from_json(text)
        if suffix in (".yaml", ".yml"):
            return cls.from_yaml(text)
        raise ValueError(
            f"AgentSpecLoader.from_path: unsupported suffix {suffix!r}; "
            "expected .json, .yaml, or .yml"
        )

    @classmethod
    def to_json(cls, spec: AgentSpec, *, indent: int | None = 2) -> str:
        """Serialise ``spec`` to a JSON object string."""
        if not isinstance(spec, AgentSpec):
            raise TypeError(
                f"AgentSpecLoader.to_json: spec must be an AgentSpec, got {type(spec).__name__}"
            )
        return json.dumps(spec.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def to_yaml(cls, spec: AgentSpec) -> str:
        """Serialise ``spec`` to a YAML mapping string.

        Raises:
            ImportError: If the ``yaml`` extra (PyYAML) is not installed.
        """
        if not isinstance(spec, AgentSpec):
            raise TypeError(
                f"AgentSpecLoader.to_yaml: spec must be an AgentSpec, got {type(spec).__name__}"
            )
        yaml = _require("yaml", "yaml")
        return yaml.safe_dump(spec.to_dict(), sort_keys=True)
