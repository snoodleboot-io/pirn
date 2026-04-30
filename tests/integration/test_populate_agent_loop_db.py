"""Populate examples/pirn.db with agent_loop runs for the explorer."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "examples" / "llm_agent"))
from agent_loop import TASKS, AgentState, build_tapestry  # noqa: E402

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.run_request import RunRequest

DB = Path(__file__).parent.parent.parent / "examples" / "pirn.db"


@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("task", TASKS)
async def test_run_to_db(task: str, seed: int) -> None:
    history = SQLiteHistory(path=str(DB))
    try:
        t = build_tapestry(history=history)
        state = AgentState(task=task, run_seed=seed)
        r = await t.run(RunRequest(parameters={"state": state}))
        assert r.succeeded, f"seed={seed} task={task!r}: {r.exceptions}"
        final: AgentState = r.outputs["agent_loop"]
        assert final.done
    finally:
        history.close()
