"""Unit tests for :class:`AgentNestingConfig` defaults and validation."""

from __future__ import annotations

import dataclasses

import pytest
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.agent.agent_nesting_config import AgentNestingConfig


class TestAgentNestingConfig:
    def test_default_cap(self) -> None:
        assert AgentNestingConfig().max_depth == 8

    def test_overridable(self) -> None:
        assert AgentNestingConfig(max_depth=3).max_depth == 3

    @pytest.mark.parametrize("bad", [0, -1, True, 2.5, "8"])
    def test_bad_max_depth_rejected(self, bad: object) -> None:
        with pytest.raises(ValueError, match="max_depth"):
            AgentNestingConfig(max_depth=bad)  # type: ignore[arg-type]

    def test_audit_dict(self) -> None:
        assert AgentNestingConfig(max_depth=2)._pirn_audit_dict() == {"max_depth": 2}

    def test_frozen_opaque_value(self) -> None:
        config = AgentNestingConfig()

        assert isinstance(config, PirnOpaqueValue)
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.max_depth = 1  # type: ignore[misc]

    def test_value_equality(self) -> None:
        assert AgentNestingConfig(max_depth=4) == AgentNestingConfig(max_depth=4)
