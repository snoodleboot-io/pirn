"""Tests for :class:`TrajectoryStep` and :class:`Trajectory` value types."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.trajectory import Trajectory
from pirn_agents.evaluation.trajectory_step import TrajectoryStep


class TrajectoryStepTests(unittest.TestCase):
    def test_stores_fields(self) -> None:
        step = TrajectoryStep(tool_name="search", arguments={"q": "x"}, result="hit")
        assert step.tool_name == "search"
        assert step.arguments == {"q": "x"}
        assert step.result == "hit"

    def test_arguments_default_empty(self) -> None:
        assert TrajectoryStep(tool_name="t").arguments == {}

    def test_non_str_tool_name_raises(self) -> None:
        with self.assertRaises(TypeError):
            TrajectoryStep(tool_name=1)  # type: ignore[arg-type]

    def test_non_mapping_arguments_raises(self) -> None:
        with self.assertRaises(TypeError):
            TrajectoryStep(tool_name="t", arguments=[1, 2])  # type: ignore[arg-type]

    def test_audit_dict_is_primitive(self) -> None:
        step = TrajectoryStep(tool_name="t", arguments={"a": 1}, result=5)
        assert step._pirn_audit_dict() == {"tool_name": "t", "arguments": {"a": 1}, "result": "5"}


class TrajectoryTests(unittest.TestCase):
    def test_normalizes_steps_to_tuple_and_exposes_tool_names(self) -> None:
        traj = Trajectory(steps=[TrajectoryStep(tool_name="a"), TrajectoryStep(tool_name="b")])
        assert isinstance(traj.steps, tuple)
        assert traj.tool_names == ("a", "b")
        assert len(traj) == 2

    def test_empty_default(self) -> None:
        assert len(Trajectory()) == 0

    def test_non_sequence_steps_raises(self) -> None:
        with self.assertRaises(TypeError):
            Trajectory(steps=42)  # type: ignore[arg-type]

    def test_non_step_element_raises(self) -> None:
        with self.assertRaises(TypeError):
            Trajectory(steps=["not-a-step"])  # type: ignore[list-item]


if __name__ == "__main__":
    unittest.main()
