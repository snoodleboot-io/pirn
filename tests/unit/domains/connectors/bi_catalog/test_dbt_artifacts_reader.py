"""Unit tests for :class:`DbtArtifactsReader`.

Uses pre-loaded ``manifest=`` / ``run_results=`` mappings so no real
``target/`` directory is required on disk.
"""

from __future__ import annotations

import pytest

from pirn.domains.connectors.bi_catalog.dbt_artifacts_config import (
    DbtArtifactsConfig,
)
from pirn.domains.connectors.bi_catalog.dbt_artifacts_reader import (
    DbtArtifactsReader,
)


def test_construction_requires_config_or_preloaded_data() -> None:
    with pytest.raises(TypeError, match="config= or pre-loaded"):
        DbtArtifactsReader()


def test_sensitive_fields_listed() -> None:
    assert DbtArtifactsConfig.sensitive_fields == ()


@pytest.mark.asyncio
class TestLoadManifest:
    async def test_returns_preloaded_manifest(self) -> None:
        manifest = {"nodes": {"model.foo.bar": {"unique_id": "model.foo.bar"}}}
        reader = DbtArtifactsReader(manifest=manifest)

        result = await reader.load_manifest()

        assert result == manifest

    async def test_top_level_dict_is_not_aliased(self) -> None:
        manifest = {"nodes": {}}
        reader = DbtArtifactsReader(manifest=manifest)

        result = await reader.load_manifest()
        result["new_top_level"] = "added"

        assert "new_top_level" not in manifest


@pytest.mark.asyncio
class TestLoadRunResults:
    async def test_returns_preloaded_run_results(self) -> None:
        run_results = {"results": [{"status": "success"}]}
        reader = DbtArtifactsReader(run_results=run_results)

        result = await reader.load_run_results()

        assert result == run_results


@pytest.mark.asyncio
class TestDiskFallback:
    async def test_load_manifest_without_data_or_path_raises(self) -> None:
        reader = DbtArtifactsReader(config=DbtArtifactsConfig())
        with pytest.raises(RuntimeError, match="target_path"):
            await reader.load_manifest()

    async def test_load_run_results_without_data_or_path_raises(self) -> None:
        reader = DbtArtifactsReader(config=DbtArtifactsConfig())
        with pytest.raises(RuntimeError, match="target_path"):
            await reader.load_run_results()


class TestCredentialSafety:
    def test_repr_does_not_crash(self) -> None:
        cfg = DbtArtifactsConfig(target_path="/tmp/dbt/target")
        # No sensitive fields — repr is just a smoke test.
        assert "DbtArtifactsConfig" in repr(cfg)
