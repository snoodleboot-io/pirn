"""Prove the WS6a headline example actually works: tapestry-check + a real run.

``examples/agents_core_pipeline/`` is the "an agent pipeline written as a
core YAML file, validated by tapestry-check" deliverable (ADR
agents-speaks-core WS6a — see ``agents-vocabulary-drift-20260913.md``'s
authoring-surfaces addendum). It lives under the repo-root ``examples/`` tree,
matching every sibling pipeline example there (``examples/content_moderation``,
``examples/llm_agent``), not under this package — so this test reaches it by
filesystem path rather than by package import, and loads it the same way
``tapestry-check`` itself does (``MODULE:FUNCTION``, imported by path).
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType

from pirn.check.validator import validate_tapestry
from pirn.core.run_request import RunRequest

from pirn_agents.types.messaging.agent_message import AgentMessage

#: packages/pirn-agents/tests/builder/<this file> -> repo root -> examples/...
_EXAMPLE_DIR = Path(__file__).resolve().parents[4] / "examples" / "agents_core_pipeline"


class _ExampleLoader:
    """Imports ``examples/agents_core_pipeline/build_tapestry.py`` by path."""

    @staticmethod
    def load() -> ModuleType:
        """Return the freshly-imported example module."""
        module_path = _EXAMPLE_DIR / "build_tapestry.py"
        spec = importlib.util.spec_from_file_location("agents_core_pipeline_example", module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load example module from {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module


class TestTheCoreYamlPipelineExample(unittest.IsolatedAsyncioTestCase):
    """The WS6a headline: an agent pipeline written as a core YAML file."""

    def test_the_example_files_exist(self) -> None:
        """Guard: the path derivation above is not silently wrong."""
        assert (_EXAMPLE_DIR / "tapestry.yaml").is_file()
        assert (_EXAMPLE_DIR / "build_tapestry.py").is_file()

    def test_tapestry_check_validates_it(self) -> None:
        # Arrange / Act
        module = _ExampleLoader.load()
        result = validate_tapestry(module.build_tapestry())

        # Assert: the same check pirn.check.main / `tapestry-check` runs.
        assert result.ok, result.issues
        assert not result.errors

    def test_the_pattern_node_names_react_by_the_short_name(self) -> None:
        """The point of the example: callable: react, no agents-only schema."""
        # Arrange / Act
        tapestry = _ExampleLoader.load().build_tapestry()
        knots = {knot.knot_id: knot for knot in tapestry._store.all()}

        # Assert
        assert "agent" in knots
        from pirn_agents.specializations.react.react_loop import ReActLoop

        assert isinstance(knots["agent"], ReActLoop)

    async def test_it_actually_runs_and_answers(self) -> None:
        # Arrange
        module = _ExampleLoader.load()
        tapestry = module.build_tapestry()
        seed = (AgentMessage(role="user", content="What is the capital of France?"),)

        # Act
        run = await tapestry.run(RunRequest(parameters={"seed_messages": seed}))

        # Assert
        assert run.succeeded, run.exceptions
        assert run.outputs["agent"].content == "Paris"


if __name__ == "__main__":
    unittest.main()
