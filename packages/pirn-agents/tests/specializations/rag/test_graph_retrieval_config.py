"""Unit tests for :class:`GraphRetrievalConfig` defaults and validation."""

from __future__ import annotations

import dataclasses

import pytest
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.specializations.rag.graph_retrieval_config import GraphRetrievalConfig


class TestGraphRetrievalConfig:
    def test_default_breadth(self) -> None:
        assert GraphRetrievalConfig().top_k == 25

    def test_overridable(self) -> None:
        assert GraphRetrievalConfig(top_k=5).top_k == 5

    @pytest.mark.parametrize("bad", [0, -1, True, 1.5, "25"])
    def test_bad_top_k_rejected(self, bad: object) -> None:
        with pytest.raises(ValueError, match="top_k"):
            GraphRetrievalConfig(top_k=bad)  # type: ignore[arg-type]

    def test_audit_dict(self) -> None:
        assert GraphRetrievalConfig(top_k=7)._pirn_audit_dict() == {"top_k": 7}

    def test_frozen_opaque_value(self) -> None:
        config = GraphRetrievalConfig()

        assert isinstance(config, PirnOpaqueValue)
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.top_k = 1  # type: ignore[misc]

    def test_value_equality(self) -> None:
        assert GraphRetrievalConfig(top_k=9) == GraphRetrievalConfig(top_k=9)
