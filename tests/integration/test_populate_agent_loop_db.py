"""Populate examples/pirn.db with agent_loop session runs for the explorer."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "examples" / "llm_agent"))
from agent_loop import SESSION_COMPLETE_ID, SessionContext, build_tapestry, make_session  # noqa: I001

from pirn.backends.sqlite.sqlite_history import SQLiteHistory

DB = Path(__file__).parent.parent.parent / "examples" / "pirn.db"


@pytest.mark.parametrize("seed", [1, 2, 3])
async def test_run_session_to_db(seed: int) -> None:
    history = SQLiteHistory(path=str(DB))
    try:
        ctx = make_session(run_seed=seed)
        t = build_tapestry(initial_ctx=ctx, history=history)
        r = await t.run(extensible=True)
        assert r.succeeded, f"seed={seed}: {r.exceptions}"
        final: SessionContext = r.outputs[SESSION_COMPLETE_ID]
        assert final.done
        assert len(final.responses) > 0
    finally:
        history.close()
