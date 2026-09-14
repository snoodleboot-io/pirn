# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``AgentSpecLoader`` — parse/serialise :class:`AgentSpec` from JSON and YAML.

JSON support uses only the standard library. YAML support is lazily provided
by the optional ``yaml`` extra (PyYAML); importing this module — and importing
``pirn_agents`` as a whole — never pulls in PyYAML, so the base install stays
backend-free. The YAML backend is imported the first time :meth:`from_yaml` or
:meth:`to_yaml` is called, via the shared :meth:`~pirn_agents._internal.optional_import.OptionalImport.require` helper, which raises
a friendly ``pip install "pirn-agents[yaml]"`` message when it is absent.

One dialect, one return type (ADR agents-speaks-core WS6a). Every ``from_*``
method here returns an :class:`AgentSpec`, parsed from a core pipeline
document — a top-level ``nodes:`` list, exactly like any other pipeline
``pirn.yaml_loader.pipeline_loader.PipelineLoader.load_yaml`` reads, in the
single-knot-plus-tagged-parameters shape
:meth:`~pirn_agents.builder.agent_spec.AgentSpec.to_pipeline_spec` writes
(see that method's docstring, and the agents section of
``docs/guides/yaml-pipelines.md``, for the exact shape). Validated as a core
``PipelineSpec`` and converted via
:meth:`~pirn_agents.builder.agent_spec.AgentSpec.from_pipeline_spec`.

The legacy flat dialect — a top-level ``pattern``/``llm``/``memory``/
``tools``/``components``/``options`` mapping, with no converter to core's own
vocabulary — was accepted here for one deprecation cycle and is now deleted
(PIR-864); a mapping with no top-level ``nodes`` key is rejected.
:meth:`~pirn_agents.builder.agent_spec.AgentSpec.from_dict` still constructs
an :class:`AgentSpec` directly from that flat shape for a caller that already
has one in hand — only this loader's text-parsing dispatch onto it is gone.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pirn.yaml_loader.specs.pipeline_spec import PipelineSpec

from pirn_agents._internal.json_shape import JsonShape
from pirn_agents._internal.optional_import import OptionalImport
from pirn_agents.builder.agent_spec import AgentSpec
from pirn_agents.tools.filesystem._path_guard import PathGuard


class AgentSpecLoader:
    """Loader/serialiser bridging :class:`AgentSpec` and JSON/YAML text."""

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> AgentSpec:
        """Build an :class:`AgentSpec` from an already-parsed core pipeline document.

        Raises:
            TypeError: If ``data`` is not a mapping.
            ValueError: If ``data`` has no top-level ``"nodes"`` key (the
                legacy flat dialect, deleted PIR-864), or the pipeline
                document is otherwise invalid (see
                :meth:`~pirn_agents.builder.agent_spec.AgentSpec.from_pipeline_spec`).
        """
        if not isinstance(data, Mapping):
            raise TypeError(
                f"AgentSpecLoader.from_mapping: data must be a mapping, got {type(data).__name__}"
            )
        if "nodes" not in data:
            raise ValueError(
                "AgentSpecLoader.from_mapping: expected a core pipeline document "
                "(a top-level 'nodes:' list) -- the flat {pattern, llm, memory, "
                "tools, components, options} dialect was deleted (PIR-864); see "
                "AgentSpec.to_pipeline_spec and the agents section of "
                "docs/guides/yaml-pipelines.md, or call AgentSpec.from_dict(data) "
                "directly if you already have a flat mapping in hand."
            )
        return AgentSpec.from_pipeline_spec(PipelineSpec.model_validate(dict(data)))

    @classmethod
    def from_json(cls, text: str) -> AgentSpec:
        """Parse a JSON object string into a validated :class:`AgentSpec`.

        Accepts the core pipeline document dialect described in the module
        docstring.

        Raises:
            TypeError: If the top-level JSON value is not an object.
            ValueError: If ``text`` is not valid JSON or the object is invalid.
        """
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"AgentSpecLoader.from_json: invalid JSON: {exc}") from exc
        if not JsonShape.is_dict(parsed):
            raise TypeError(
                f"AgentSpecLoader.from_json: top-level JSON must be an object, "
                f"got {type(parsed).__name__}"
            )
        return cls.from_mapping(parsed)

    @classmethod
    def from_yaml(cls, text: str) -> AgentSpec:
        """Parse a YAML mapping string into a validated :class:`AgentSpec`.

        Accepts the core pipeline document dialect described in the module
        docstring.

        Raises:
            ImportError: If the ``yaml`` extra (PyYAML) is not installed.
            TypeError: If the top-level YAML value is not a mapping.
            ValueError: If ``text`` is not valid YAML or the mapping is invalid.
        """
        yaml = OptionalImport.require("yaml", "yaml")
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f"AgentSpecLoader.from_yaml: invalid YAML: {exc}") from exc
        if not JsonShape.is_dict(parsed):
            raise TypeError(
                f"AgentSpecLoader.from_yaml: top-level YAML must be a mapping, "
                f"got {type(parsed).__name__}"
            )
        return cls.from_mapping(parsed)

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
        """Serialise ``spec`` to a core pipeline document JSON string.

        Writes the same ``nodes:``-shaped document :meth:`from_json` reads
        back (via ``spec.to_pipeline_spec()``), so ``to_json``/``from_json``
        round-trip through the one dialect this loader speaks (PIR-864).
        """
        if not isinstance(spec, AgentSpec):
            raise TypeError(
                f"AgentSpecLoader.to_json: spec must be an AgentSpec, got {type(spec).__name__}"
            )
        return json.dumps(
            spec.to_pipeline_spec().model_dump(mode="json"), indent=indent, sort_keys=True
        )

    @classmethod
    def to_yaml(cls, spec: AgentSpec) -> str:
        """Serialise ``spec`` to a core pipeline document YAML string.

        Writes the same ``nodes:``-shaped document :meth:`from_yaml` reads
        back (via ``spec.to_pipeline_spec()``), so ``to_yaml``/``from_yaml``
        round-trip through the one dialect this loader speaks (PIR-864).

        Raises:
            ImportError: If the ``yaml`` extra (PyYAML) is not installed.
        """
        if not isinstance(spec, AgentSpec):
            raise TypeError(
                f"AgentSpecLoader.to_yaml: spec must be an AgentSpec, got {type(spec).__name__}"
            )
        yaml = OptionalImport.require("yaml", "yaml")
        return yaml.safe_dump(spec.to_pipeline_spec().model_dump(mode="json"), sort_keys=True)
