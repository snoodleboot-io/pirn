"""Local-file parser for dbt artifacts (``manifest.json``, ``run_results.json``).

Unlike the other BI / catalog connectors in this package, ``DbtArtifactsReader``
is **not** an :class:`~pirn.connectors.api_client.ApiClient` — dbt
artifacts live on disk after a ``dbt run``/``dbt build``. The reader uses
``json`` from the standard library (run inside :func:`asyncio.to_thread` so the
event loop is not blocked on disk I/O) and therefore needs no extra
dependency. Tests inject pre-loaded ``manifest=`` / ``run_results=`` mappings;
production usage points :class:`DbtArtifactsConfig.target_path` at a real
``target/`` directory.

Besides the raw :meth:`load_manifest` / :meth:`load_run_results` accessors
(``run_results.json`` has no catalog equivalent), the reader implements the :class:`MetadataCatalog` capability so
that downstream knots can iterate dbt nodes through the same interface
they use for DataHub / OpenMetadata / Alation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator, Mapping
from typing import Any, ClassVar

from pirn.connectors.bi_catalog.dbt_artifacts_config import (
    DbtArtifactsConfig,
)
from pirn.connectors.capabilities.metadata_catalog import (
    MetadataCatalog,
)
from pirn.core.shape_guard import ShapeGuard


class DbtArtifactsReader(MetadataCatalog):
    """Async reader for dbt's ``manifest.json`` and ``run_results.json``.

    Construct with either:

    * ``DbtArtifactsReader(config=DbtArtifactsConfig(target_path=...))`` —
      load JSON from disk inside :func:`asyncio.to_thread`.
    * ``DbtArtifactsReader(manifest=..., run_results=...)`` — provide
      pre-loaded dicts (test or in-memory usage). Either or both may be
      provided; missing artifacts raise at load time.

    The :class:`MetadataCatalog` surface exposes manifest entries:

    * :meth:`list_entities` accepts ``"model"``, ``"seed"``, ``"snapshot"``,
      ``"test"`` (filtered from ``manifest["nodes"]`` by ``resource_type``)
      and ``"source"`` (read from ``manifest["sources"]``).
    * :meth:`describe_entity` looks up an entity by its dbt node key
      (e.g. ``"model.my_project.my_model"``) in either ``nodes`` or
      ``sources``.
    """

    _manifest_filename: ClassVar[str] = "manifest.json"
    _run_results_filename: ClassVar[str] = "run_results.json"
    _node_resource_types: ClassVar[frozenset[str]] = frozenset(
        {"model", "seed", "snapshot", "test"}
    )

    def __init__(
        self,
        config: DbtArtifactsConfig | None = None,
        *,
        manifest: Mapping[str, object] | None = None,
        run_results: Mapping[str, object] | None = None,
    ) -> None:
        if config is None and manifest is None and run_results is None:
            raise TypeError(
                "DbtArtifactsReader requires either config= or pre-loaded manifest=/run_results="
            )
        if config is not None and config.target_path is not None:
            self._validate_target_path(config.target_path)
        self._config = config
        self._manifest: dict[str, object] | None = dict(manifest) if manifest is not None else None
        self._run_results: dict[str, object] | None = (
            dict(run_results) if run_results is not None else None
        )
        self._logger = logging.getLogger(self.__class__.__module__)

    @staticmethod
    def _validate_target_path(target_path: str) -> None:
        """Reject ``target_path`` values that could escape the dbt directory.

        ``..`` segments are refused outright. Defence-in-depth — the
        operator owns this config but a misconfiguration could otherwise
        let ``_artifact_path`` resolve outside the intended dbt project.
        """
        if any(part == ".." for part in target_path.split(os.sep)):
            raise ValueError(
                "DbtArtifactsReader: config.target_path must not contain '..' segments"
            )

    @property
    def config(self) -> DbtArtifactsConfig | None:
        return self._config

    async def load_manifest(self) -> dict[str, object]:
        """Return the parsed ``manifest.json`` contents."""
        if self._manifest is not None:
            return dict(self._manifest)
        path = self._artifact_path(self._manifest_filename)
        return await asyncio.to_thread(self._read_json_file, path)

    async def load_run_results(self) -> dict[str, object]:
        """Return the parsed ``run_results.json`` contents."""
        if self._run_results is not None:
            return dict(self._run_results)
        path = self._artifact_path(self._run_results_filename)
        return await asyncio.to_thread(self._read_json_file, path)

    async def list_entities(
        self,
        entity_type: str,
        *,
        filter: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        """Yield manifest entries of ``entity_type`` matching ``filter``.

        Supported ``entity_type`` values:

        * ``"model"``, ``"seed"``, ``"snapshot"``, ``"test"`` — drawn
          from ``manifest["nodes"]`` filtered by the node's
          ``resource_type``.
        * ``"source"`` — drawn from ``manifest["sources"]``.
        """
        manifest = await self.load_manifest()
        if entity_type == "source":
            entries = list(self._section(manifest, "sources").values())
        elif entity_type in self._node_resource_types:
            entries = [
                node
                for node in self._section(manifest, "nodes").values()
                if node.get("resource_type") == entity_type
            ]
        else:
            raise ValueError(
                "DbtArtifactsReader: unsupported entity_type "
                f"{entity_type!r}; expected one of "
                "'model', 'seed', 'snapshot', 'test', 'source'"
            )
        for entry in entries:
            if filter is None or self._matches_filter(entry, filter):
                yield entry

    async def describe_entity(
        self,
        entity_id: str,
    ) -> Mapping[str, Any]:
        """Return the manifest entry whose key is ``entity_id``.

        Looks first in ``manifest["nodes"]``, then ``manifest["sources"]``.
        Raises :class:`KeyError` if neither contains ``entity_id``.
        """
        manifest = await self.load_manifest()
        nodes = self._section(manifest, "nodes")
        if entity_id in nodes:
            return nodes[entity_id]
        sources = self._section(manifest, "sources")
        if entity_id in sources:
            return sources[entity_id]
        raise KeyError(
            f"DbtArtifactsReader: entity_id {entity_id!r} not found in manifest nodes or sources"
        )

    @staticmethod
    def _section(manifest: Mapping[str, object], key: str) -> dict[str, Mapping[str, Any]]:
        """Return the mapping entries of ``manifest[key]`` (``{}`` when absent or malformed)."""
        section = manifest.get(key)
        if not ShapeGuard.is_str_keyed_mapping(section):
            return {}
        return {
            entry_key: entry
            for entry_key, entry in section.items()
            if ShapeGuard.is_str_keyed_mapping(entry)
        }

    @staticmethod
    def _matches_filter(entity: Mapping[str, Any], filter: Mapping[str, Any]) -> bool:
        for key, value in filter.items():
            if entity.get(key) != value:
                return False
        return True

    def _artifact_path(self, filename: str) -> str:
        if self._config is None or self._config.target_path is None:
            raise RuntimeError(
                f"DbtArtifactsReader: config.target_path is required to read {filename} from disk"
            )
        return os.path.join(self._config.target_path, filename)

    @staticmethod
    def _read_json_file(path: str) -> dict[str, object]:
        with open(path, encoding="utf-8") as handle:
            payload: object = json.load(handle)
        if not ShapeGuard.is_str_keyed_mapping(payload):
            raise ValueError(f"DbtArtifactsReader: {path} does not contain a JSON object")
        return dict(payload)
