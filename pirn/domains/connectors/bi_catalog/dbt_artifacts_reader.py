"""Local-file parser for dbt artifacts (``manifest.json``, ``run_results.json``).

Unlike the other BI / catalog connectors in this package, ``DbtArtifactsReader``
is **not** an :class:`~pirn.domains.connectors.api_client.ApiClient` — dbt
artifacts live on disk after a ``dbt run``/``dbt build``. The reader uses
``json`` from the standard library (run inside :func:`asyncio.to_thread` so the
event loop is not blocked on disk I/O) and therefore needs no extra
dependency. Tests inject pre-loaded ``manifest=`` / ``run_results=`` mappings;
production usage points :class:`DbtArtifactsConfig.target_path` at a real
``target/`` directory.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import ClassVar, Mapping

from pirn.domains.connectors.bi_catalog.dbt_artifacts_config import (
    DbtArtifactsConfig,
)


class DbtArtifactsReader:
    """Async reader for dbt's ``manifest.json`` and ``run_results.json``.

    Construct with either:

    * ``DbtArtifactsReader(config=DbtArtifactsConfig(target_path=...))`` —
      load JSON from disk inside :func:`asyncio.to_thread`.
    * ``DbtArtifactsReader(manifest=..., run_results=...)`` — provide
      pre-loaded dicts (test or in-memory usage). Either or both may be
      provided; missing artifacts raise at load time.
    """

    _manifest_filename: ClassVar[str] = "manifest.json"
    _run_results_filename: ClassVar[str] = "run_results.json"

    def __init__(
        self,
        config: DbtArtifactsConfig | None = None,
        *,
        manifest: Mapping | None = None,
        run_results: Mapping | None = None,
    ) -> None:
        if config is None and manifest is None and run_results is None:
            raise TypeError(
                "DbtArtifactsReader requires either config= or pre-loaded "
                "manifest=/run_results="
            )
        self._config = config
        self._manifest = dict(manifest) if manifest is not None else None
        self._run_results = (
            dict(run_results) if run_results is not None else None
        )
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> DbtArtifactsConfig | None:
        return self._config

    async def load_manifest(self) -> dict:
        """Return the parsed ``manifest.json`` contents."""
        if self._manifest is not None:
            return dict(self._manifest)
        path = self._artifact_path(self._manifest_filename)
        return await asyncio.to_thread(self._read_json_file, path)

    async def load_run_results(self) -> dict:
        """Return the parsed ``run_results.json`` contents."""
        if self._run_results is not None:
            return dict(self._run_results)
        path = self._artifact_path(self._run_results_filename)
        return await asyncio.to_thread(self._read_json_file, path)

    def _artifact_path(self, filename: str) -> str:
        if self._config is None or self._config.target_path is None:
            raise RuntimeError(
                "DbtArtifactsReader: config.target_path is required to read "
                f"{filename} from disk"
            )
        return os.path.join(self._config.target_path, filename)

    @staticmethod
    def _read_json_file(path: str) -> dict:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
