"""Worker process for the two-interpreter tool record/replay test (PIR-840).

Run as a script, never imported by the suite::

    python _cross_process_replay_worker.py <record|replay> <workdir> <scenario> [<scenario> ...]

Each scenario builds its own tapestry over ``SQLiteHistory(<workdir>/<scenario>/h.db)``
and ``LocalDiskDataStore(<workdir>/<scenario>/values)``. ``record`` runs it and stores
the run id; ``replay`` loads that run in *this* process and runs the same graph with
``replay=``. The worker prints one JSON object mapping each scenario to its outcome.

Every tool call that really executes appends a line to ``<workdir>/invocations.log``,
so the parent can tell a served replay from a re-invocation across the process
boundary.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from pirn.backends.disk import LocalDiskDataStore
from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.recording.replay_error import ReplayError
from pirn.recording.replay_session import ReplaySession
from pirn.tapestry import Tapestry

from pirn_agents.planning.tool_executor import ToolExecutor
from pirn_agents.tools.calculator.calculator_tool import CalculatorTool
from pirn_agents.tools.filesystem.read_file_tool import ReadFileTool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_decorator import tool
from pirn_agents.tools.tool_invocation import ToolInvocation


def _log_invocation(label: str) -> None:
    """Append ``label`` to the shared invocation log named by the environment."""
    with Path(os.environ["PIRN_REPLAY_WORKDIR"], "invocations.log").open("a") as handle:
        handle.write(f"{label}\n")


@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    _log_invocation("add")
    return a + b


@tool(state={"tenant": "prod"})
def tenant_add(a: int, b: int, state: dict[str, str]) -> int:
    """Add two integers for the injected tenant."""
    _log_invocation("tenant_add")
    return a + b


@knot
async def make_call(**_: Any) -> ToolCall:
    """Emit the tool call from an upstream knot rather than a literal."""
    return ToolCall(tool_name="add", arguments={"a": 1, "b": 2}, call_id="c1")


class ReplayWorker:
    """Build, record and replay one scenario per call."""

    def __init__(self, *, mode: str, workdir: Path) -> None:
        self._mode = mode
        self._workdir = workdir

    def build(self, scenario: str) -> Tapestry:
        """Return the tapestry for ``scenario`` over a SQLite history and disk store."""
        scenario_dir = self._workdir / scenario
        scenario_dir.mkdir(parents=True, exist_ok=True)
        tapestry = Tapestry(
            history=SQLiteHistory(path=str(scenario_dir / "h.db")),
            data_store=LocalDiskDataStore(scenario_dir / "values", allow_unsigned=True),
        )
        literal = ToolCall(tool_name="add", arguments={"a": 1, "b": 2}, call_id="c1")
        with tapestry:
            if scenario == "literal_call":
                ToolInvocation(tool=add, call=literal, _config=KnotConfig(id="invoke"))
            elif scenario == "upstream_call":
                upstream = make_call(_config=KnotConfig(id="make-call"))
                ToolInvocation(tool=add, call=upstream, _config=KnotConfig(id="invoke"))
            elif scenario == "tool_executor":
                upstream = make_call(_config=KnotConfig(id="make-call"))
                ToolExecutor(
                    call=upstream,
                    tools=[add, CalculatorTool()],
                    _config=KnotConfig(id="invoke"),
                )
            elif scenario == "read_file_root_swap":
                root = scenario_dir / ("root_a" if self._mode == "record" else "root_b")
                root.mkdir(exist_ok=True)
                (root / "note.txt").write_text(f"content of {root.name}")
                call = ToolCall(tool_name="read_file", arguments={"path": "note.txt"}, call_id="c1")
                ToolInvocation(
                    tool=ReadFileTool(root=root), call=call, _config=KnotConfig(id="invoke")
                )
            elif scenario == "stateful_tool":
                call = ToolCall(tool_name="tenant_add", arguments={"a": 1, "b": 2}, call_id="c1")
                ToolInvocation(tool=tenant_add, call=call, _config=KnotConfig(id="invoke"))
            else:
                raise SystemExit(f"unknown scenario {scenario!r}")
        return tapestry

    async def run(self, scenario: str) -> dict[str, Any]:
        """Record or replay ``scenario`` and return a JSON-friendly summary."""
        tapestry = self.build(scenario)
        run_id_file = self._workdir / scenario / "run_id"
        if self._mode == "record":
            result = await tapestry.run(RunRequest())
            run_id_file.write_text(result.run_id)
            return {"outcome": "RECORDED", "output": self._describe(result.outputs["invoke"])}
        session = await ReplaySession.from_history(
            history=tapestry.history, run_id=run_id_file.read_text()
        )
        try:
            result = await tapestry.run(RunRequest(), replay=session)
        except ReplayError as exc:
            return {"outcome": "REFUSED", "error": type(exc).__name__}
        return {"outcome": "SERVED", "output": self._describe(result.outputs["invoke"])}

    @staticmethod
    def _describe(output: Any) -> Any:
        """Reduce a knot output to the tool values it carries, for comparison."""
        if isinstance(output, (list, tuple)):
            return [ReplayWorker._describe(item) for item in output]
        return {"call_id": output.call_id, "status": str(output.status), "result": output.result}


async def main(argv: list[str]) -> None:
    """Entry point: ``<mode> <workdir> <scenario>...``."""
    mode, workdir, *scenarios = argv
    worker = ReplayWorker(mode=mode, workdir=Path(workdir))
    summary = {scenario: await worker.run(scenario) for scenario in scenarios}
    print(json.dumps(summary))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
