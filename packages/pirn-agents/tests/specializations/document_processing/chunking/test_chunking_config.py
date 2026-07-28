"""Unit tests for :class:`ChunkingConfig` defaults and validation."""

from __future__ import annotations

import dataclasses

import pytest
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.specializations.document_processing.chunking.chunking_config import (
    ChunkingConfig,
)


class TestChunkingConfig:
    def test_default_geometry(self) -> None:
        config = ChunkingConfig()

        assert config.chunk_size == 1000
        assert config.chunk_overlap == 100

    def test_overridable(self) -> None:
        config = ChunkingConfig(chunk_size=200, chunk_overlap=0)

        assert config.chunk_size == 200
        assert config.chunk_overlap == 0

    @pytest.mark.parametrize("bad", [0, -1, True, 10.5, "1000"])
    def test_bad_chunk_size_rejected(self, bad: object) -> None:
        with pytest.raises(ValueError, match="chunk_size"):
            ChunkingConfig(chunk_size=bad)  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad", [-1, True, 10.5, "100"])
    def test_bad_chunk_overlap_rejected(self, bad: object) -> None:
        with pytest.raises(ValueError, match="chunk_overlap"):
            ChunkingConfig(chunk_overlap=bad)  # type: ignore[arg-type]

    @pytest.mark.parametrize("overlap", [100, 200])
    def test_overlap_must_be_smaller_than_window(self, overlap: int) -> None:
        with pytest.raises(ValueError, match="smaller than chunk_size"):
            ChunkingConfig(chunk_size=100, chunk_overlap=overlap)

    def test_audit_dict(self) -> None:
        assert ChunkingConfig(chunk_size=64, chunk_overlap=8)._pirn_audit_dict() == {
            "chunk_size": 64,
            "chunk_overlap": 8,
        }

    def test_frozen_opaque_value(self) -> None:
        config = ChunkingConfig()

        assert isinstance(config, PirnOpaqueValue)
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.chunk_size = 1  # type: ignore[misc]

    def test_value_equality(self) -> None:
        assert ChunkingConfig(chunk_size=50, chunk_overlap=5) == ChunkingConfig(
            chunk_size=50, chunk_overlap=5
        )
