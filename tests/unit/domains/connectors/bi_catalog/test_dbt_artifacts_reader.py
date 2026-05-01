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
from pirn.domains.connectors.capabilities.metadata_catalog import (
    MetadataCatalog,
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


def test_implements_metadata_catalog() -> None:
    reader = DbtArtifactsReader(manifest={"nodes": {}})
    assert isinstance(reader, MetadataCatalog)


@pytest.mark.asyncio
class TestListEntities:
    async def test_lists_models_filtered_by_resource_type(self) -> None:
        manifest = {
            "nodes": {
                "model.foo.a": {
                    "unique_id": "model.foo.a",
                    "resource_type": "model",
                    "name": "a",
                },
                "model.foo.b": {
                    "unique_id": "model.foo.b",
                    "resource_type": "model",
                    "name": "b",
                },
                "test.foo.t1": {
                    "unique_id": "test.foo.t1",
                    "resource_type": "test",
                    "name": "t1",
                },
                "seed.foo.s1": {
                    "unique_id": "seed.foo.s1",
                    "resource_type": "seed",
                    "name": "s1",
                },
            }
        }
        reader = DbtArtifactsReader(manifest=manifest)

        results = []
        async for entity in reader.list_entities("model"):
            results.append(entity["unique_id"])

        assert sorted(results) == ["model.foo.a", "model.foo.b"]

    async def test_lists_tests(self) -> None:
        manifest = {
            "nodes": {
                "test.foo.t1": {
                    "unique_id": "test.foo.t1",
                    "resource_type": "test",
                },
                "model.foo.a": {
                    "unique_id": "model.foo.a",
                    "resource_type": "model",
                },
            }
        }
        reader = DbtArtifactsReader(manifest=manifest)

        results = [e async for e in reader.list_entities("test")]

        assert [e["unique_id"] for e in results] == ["test.foo.t1"]

    async def test_lists_snapshots(self) -> None:
        manifest = {
            "nodes": {
                "snapshot.foo.s1": {
                    "unique_id": "snapshot.foo.s1",
                    "resource_type": "snapshot",
                }
            }
        }
        reader = DbtArtifactsReader(manifest=manifest)

        results = [e async for e in reader.list_entities("snapshot")]

        assert len(results) == 1
        assert results[0]["unique_id"] == "snapshot.foo.s1"

    async def test_lists_sources_from_sources_section(self) -> None:
        manifest = {
            "nodes": {},
            "sources": {
                "source.foo.raw_orders": {
                    "unique_id": "source.foo.raw_orders",
                    "name": "raw_orders",
                },
                "source.foo.raw_users": {
                    "unique_id": "source.foo.raw_users",
                    "name": "raw_users",
                },
            },
        }
        reader = DbtArtifactsReader(manifest=manifest)

        results = [e async for e in reader.list_entities("source")]

        assert sorted(e["unique_id"] for e in results) == [
            "source.foo.raw_orders",
            "source.foo.raw_users",
        ]

    async def test_filter_matches_key_value(self) -> None:
        manifest = {
            "nodes": {
                "model.foo.a": {
                    "unique_id": "model.foo.a",
                    "resource_type": "model",
                    "schema": "gold",
                },
                "model.foo.b": {
                    "unique_id": "model.foo.b",
                    "resource_type": "model",
                    "schema": "bronze",
                },
            }
        }
        reader = DbtArtifactsReader(manifest=manifest)

        results = [
            e
            async for e in reader.list_entities(
                "model", filter={"schema": "gold"}
            )
        ]

        assert [e["unique_id"] for e in results] == ["model.foo.a"]

    async def test_unsupported_entity_type_raises(self) -> None:
        reader = DbtArtifactsReader(manifest={"nodes": {}})

        with pytest.raises(ValueError, match="unsupported entity_type"):
            async for _ in reader.list_entities("exposure"):
                pass


@pytest.mark.asyncio
class TestDescribeEntity:
    async def test_describe_finds_node(self) -> None:
        manifest = {
            "nodes": {
                "model.foo.a": {
                    "unique_id": "model.foo.a",
                    "name": "a",
                }
            }
        }
        reader = DbtArtifactsReader(manifest=manifest)

        entity = await reader.describe_entity("model.foo.a")

        assert entity["name"] == "a"

    async def test_describe_finds_source(self) -> None:
        manifest = {
            "nodes": {},
            "sources": {
                "source.foo.s1": {"unique_id": "source.foo.s1", "name": "s1"}
            },
        }
        reader = DbtArtifactsReader(manifest=manifest)

        entity = await reader.describe_entity("source.foo.s1")

        assert entity["name"] == "s1"

    async def test_describe_missing_raises_key_error(self) -> None:
        reader = DbtArtifactsReader(manifest={"nodes": {}, "sources": {}})

        with pytest.raises(KeyError, match="not found"):
            await reader.describe_entity("model.foo.missing")
