"""Env-independent test: :meth:`AgentSpecLoader.from_yaml` without PyYAML.

Blocks the ``yaml`` import via ``sys.modules`` so the missing-backend path is
exercised whether or not PyYAML happens to be installed in this environment.
"""

from __future__ import annotations

import unittest
from unittest import mock

from pirn_agents.builder.agent_spec import AgentSpec
from pirn_agents.builder.agent_spec_loader import AgentSpecLoader


class TestAgentSpecLoaderMissingYaml(unittest.TestCase):
    def test_from_yaml_raises_friendly_error_when_backend_absent(self) -> None:
        # Arrange: mapping ``{"yaml": None}`` makes ``import yaml`` raise ImportError.
        with mock.patch.dict("sys.modules", {"yaml": None}):
            # Act / Assert
            with self.assertRaises(ImportError) as ctx:
                AgentSpecLoader.from_yaml("pattern: react")
        assert 'pip install "pirn-agents[yaml]"' in str(ctx.exception)

    def test_to_yaml_raises_friendly_error_when_backend_absent(self) -> None:
        spec = AgentSpec(pattern="react")
        with mock.patch.dict("sys.modules", {"yaml": None}):
            with self.assertRaises(ImportError) as ctx:
                AgentSpecLoader.to_yaml(spec)
        assert 'pip install "pirn-agents[yaml]"' in str(ctx.exception)

    def test_from_json_needs_no_backend(self) -> None:
        # Arrange / Act: JSON path must work even with yaml blocked.
        with mock.patch.dict("sys.modules", {"yaml": None}):
            spec = AgentSpecLoader.from_json('{"pattern": "react"}')

        # Assert
        assert spec.pattern == "react"


if __name__ == "__main__":
    unittest.main()
