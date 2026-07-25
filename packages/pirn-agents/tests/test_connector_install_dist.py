"""The ``_install_dist`` override makes agents connectors name pirn-agents (PIR-745).

``ConnectorBase`` moved to pirn-core and defaults its missing-dependency install
hint to ``pirn-core`` (verified in the core suite). Agents connectors override
``_install_dist = "pirn-agents"`` so their hint points at the right distribution.
This guards that override for the shipped agents connector bases.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.connector_base import ConnectorBase

from pirn_agents.embeddings.base_embedding_provider import BaseEmbeddingProvider
from pirn_agents.llm.base_llm_provider import BaseLLMProvider


class _AgentsConnector(ConnectorBase):
    """A bare agents-side connector carrying the distribution override."""

    _install_dist = "pirn-agents"

    async def _create_client(self) -> Any:  # pragma: no cover - not exercised
        return object()


class TestInstallDistOverride(unittest.TestCase):
    def test_agents_connector_names_pirn_agents(self) -> None:
        with self.assertRaises(ImportError) as ctx:
            _AgentsConnector()._require("vector", "nope_missing_xyz")
        assert 'pip install "pirn-agents[vector]"' in str(ctx.exception)

    def test_shipped_bases_carry_the_override(self) -> None:
        assert BaseLLMProvider._install_dist == "pirn-agents"
        assert BaseEmbeddingProvider._install_dist == "pirn-agents"


if __name__ == "__main__":
    unittest.main()
