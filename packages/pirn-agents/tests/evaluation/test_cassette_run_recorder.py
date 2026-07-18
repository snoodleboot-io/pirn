"""Mirrored test: F29's cassette recorder closes F12's ``RunRecorder`` seam.

Drives :func:`run_eval` with a :class:`CassetteRunRecorder` in RECORD mode over a
call-counting target, then replays the captured cassette in a fresh recorder and
asserts the report is identical with **zero** further target calls — i.e. the eval
suite is deterministic and offline.
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn_agents.determinism.recording_mode import RecordingMode
from pirn_agents.evaluation.cassette_run_recorder import CassetteRunRecorder
from pirn_agents.evaluation.eval_dataset import EvalDataset
from pirn_agents.evaluation.eval_item import EvalItem
from pirn_agents.evaluation.exact_match import exact_match
from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.run_eval import run_eval
from pirn_agents.evaluation.run_recorder import RunRecorder


def _dataset() -> EvalDataset:
    return EvalDataset(
        items=(
            EvalItem(item_id="q1", input={"q": "france"}, expected={"answer": "Paris"}),
            EvalItem(item_id="q2", input={"q": "japan"}, expected={"answer": "Tokyo"}),
        )
    )


class _CountingTarget:
    """A target that records how many live invocations happened."""

    def __init__(self) -> None:
        self.calls = 0
        self._answers = {"france": "Paris", "japan": "Tokyo"}

    async def __call__(self, item_input: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls += 1
        return {"answer": self._answers[str(item_input["q"])]}


def _em(item: EvalItem, output: Mapping[str, Any]) -> MetricResult:
    return exact_match(str(output["answer"]), str(item.expected["answer"]))


class CassetteRunRecorderSeamTests(unittest.IsolatedAsyncioTestCase):
    async def test_is_a_run_recorder(self) -> None:
        assert isinstance(CassetteRunRecorder.recording(), RunRecorder)

    async def test_record_then_replay_is_deterministic_and_offline(self) -> None:
        target = _CountingTarget()
        rec = CassetteRunRecorder.recording()
        recorded = await run_eval(
            dataset=_dataset(), target=target, metrics={"exact_match": _em}, recorder=rec
        )
        assert target.calls == 2
        assert recorded.metric("exact_match") == 1.0

        # Replay from the captured cassette: no further live target calls.
        replay_target = _CountingTarget()
        replayer = CassetteRunRecorder.replaying(rec.cassette)
        replayed = await run_eval(
            dataset=_dataset(),
            target=replay_target,
            metrics={"exact_match": _em},
            recorder=replayer,
        )
        assert replay_target.calls == 0
        assert [r.item_id for r in replayed.results] == ["q1", "q2"]
        assert replayed.metric("exact_match") == recorded.metric("exact_match")

    async def test_replay_missing_entry_raises(self) -> None:
        from pirn_agents.determinism.cassette import Cassette
        from pirn_agents.exceptions.missing_cassette_entry_error import MissingCassetteEntryError

        replayer = CassetteRunRecorder.replaying(Cassette())
        with self.assertRaises(MissingCassetteEntryError):
            await run_eval(
                dataset=_dataset(),
                target=_CountingTarget(),
                metrics={"exact_match": _em},
                recorder=replayer,
            )

    async def test_mode_flows_through(self) -> None:
        rec = CassetteRunRecorder.recording()
        assert rec._recorder.mode is RecordingMode.RECORD


if __name__ == "__main__":
    unittest.main()
