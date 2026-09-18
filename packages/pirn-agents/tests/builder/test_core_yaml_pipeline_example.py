"""Prove the WS6a headline example actually works: validation + a real run.

``examples/agents_core_pipeline/`` is the "an agent pipeline written as a
core YAML file, validated by tapestry-check" deliverable (ADR
agents-speaks-core WS6a — see ``agents-vocabulary-drift-20260913.md``'s
authoring-surfaces addendum). It lives under the repo-root ``examples/`` tree,
matching every sibling pipeline example there (``examples/content_moderation``,
``examples/llm_agent``), not under this package — so this test puts the
workspace root on ``sys.path`` and imports it as the ``examples`` package, the
same way ``python -m examples.agents_core_pipeline`` runs it from the repo root.
"""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from types import ModuleType

from pirn.check.tapestry_validator import TapestryValidator
from pirn.core.run_request import RunRequest

from pirn_agents.types.messaging.agent_message import AgentMessage

#: packages/pirn-agents/tests/builder/<this file> -> repo root -> examples/...
_WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
_EXAMPLE_DIR = _WORKSPACE_ROOT / "examples" / "agents_core_pipeline"


class _ExampleLoader:
    """Imports ``examples.agents_core_pipeline.agents_core_pipeline`` from the workspace root."""

    @staticmethod
    def load() -> ModuleType:
        """Return the imported example module (it defines ``AgentsCorePipeline``)."""
        if str(_WORKSPACE_ROOT) not in sys.path:
            sys.path.insert(0, str(_WORKSPACE_ROOT))
        return importlib.import_module("examples.agents_core_pipeline.agents_core_pipeline")


class TestTheCoreYamlPipelineExample(unittest.IsolatedAsyncioTestCase):
    """The WS6a headline: an agent pipeline written as a core YAML file."""

    def test_the_example_files_exist(self) -> None:
        """Guard: the path derivation above is not silently wrong."""
        assert (_EXAMPLE_DIR / "tapestry.yaml").is_file()
        assert (_EXAMPLE_DIR / "agents_core_pipeline.py").is_file()

    def test_tapestry_check_validates_it(self) -> None:
        # Arrange / Act
        module = _ExampleLoader.load()
        result = TapestryValidator.validate(module.AgentsCorePipeline.build_tapestry())

        # Assert: the same check pirn.check.tapestry_check_cli / `tapestry-check` runs.
        assert result.ok, result.issues
        assert not result.errors

    def test_the_pattern_node_names_react_by_the_short_name(self) -> None:
        """The point of the example: callable: react, no agents-only schema."""
        # Arrange / Act
        tapestry = _ExampleLoader.load().AgentsCorePipeline.build_tapestry()
        knots = {knot.knot_id: knot for knot in tapestry._store.all()}

        # Assert
        assert "agent" in knots
        from pirn_agents.specializations.react.react_loop import ReActLoop

        assert isinstance(knots["agent"], ReActLoop)

    async def test_it_actually_runs_and_answers(self) -> None:
        # Arrange
        module = _ExampleLoader.load()
        tapestry = module.AgentsCorePipeline.build_tapestry()
        seed = (AgentMessage(role="user", content="What is the capital of France?"),)

        # Act
        run = await tapestry.run(RunRequest(parameters={"seed_messages": seed}))

        # Assert
        assert run.succeeded, run.exceptions
        assert run.outputs["agent"].data == "Paris"


if __name__ == "__main__":
    unittest.main()
