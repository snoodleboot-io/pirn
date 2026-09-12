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

``PIRN_REPLAY_TENANT`` differs between the recording and the replaying process. The
tools that depend on it, or on the mode, are the false matches found in review of
PR #310: each behaves differently in the two processes while presenting the same
name, description, schema and qualname, so each must refuse on replay. The
``main_script`` scenario is replayed from a *copy* of this file at another path,
standing in for a different script that defines a same-named tool.
"""

from __future__ import annotations

import asyncio
import functools
import json
import os
import sys
from collections.abc import Callable, Mapping
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
from pirn_agents.tools.tool import Tool
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


def scoped(tenant: str) -> Callable[[Callable[..., str]], Callable[..., str]]:
    """Return a ``functools.wraps`` decorator that binds ``tenant`` in a closure."""

    # design-decision-override: a closure-capturing decorator is the case under test.
    def decorate(fn: Callable[..., str]) -> Callable[..., str]:
        # design-decision-override: the wrapper's closure is what must not be hashed away.
        @functools.wraps(fn)
        def wrapper(query: str) -> str:
            return fn(query, tenant)

        return wrapper

    return decorate


@tool
@scoped(os.environ["PIRN_REPLAY_TENANT"])
def lookup(query: str, tenant: str = "") -> str:
    """Look up a record for the bound tenant."""
    _log_invocation("lookup")
    return f"{tenant}:{query}"


@tool
def tenant_default(query: str, tenant: str = os.environ["PIRN_REPLAY_TENANT"]) -> str:
    """Look up a record for the default tenant."""
    _log_invocation("tenant_default")
    return f"{tenant}:{query}"


@tool
def search(query: str) -> str:
    """Search the corpus."""
    _log_invocation("search")
    return f"served-by:{Path(__file__).name}:{query}"


class TenantReadFile(ReadFileTool):
    """Inherits ``ReadFileTool``'s opt-in and adds behaviour its config does not declare."""

    def __init__(self, *, root: str | Path, tenant: str) -> None:
        super().__init__(root=root)
        self._tenant = tenant

    async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        output = dict(await super().invoke(arguments))
        output["content"] = f"{self._tenant}:{output['content']}"
        return output


def make_scaled(factor: int) -> Tool:
    """Return a calculator whose class is defined per call, so every class shares a qualname."""

    # design-decision-override: a factory-local class is the case under test.
    class Scaled(CalculatorTool):
        async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
            output = dict(await super().invoke(arguments))
            output["result"] = output["result"] * factor
            return output

    return Scaled()


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
        query = {"query": "x"}
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
            elif scenario == "wrapped_closure":
                call = ToolCall(tool_name="lookup", arguments=query, call_id="c1")
                ToolInvocation(tool=lookup, call=call, _config=KnotConfig(id="invoke"))
            elif scenario == "default_argument":
                call = ToolCall(tool_name="tenant_default", arguments=query, call_id="c1")
                ToolInvocation(tool=tenant_default, call=call, _config=KnotConfig(id="invoke"))
            elif scenario == "main_script":
                call = ToolCall(tool_name="search", arguments=query, call_id="c1")
                ToolInvocation(tool=search, call=call, _config=KnotConfig(id="invoke"))
            elif scenario == "inherited_opt_in":
                (scenario_dir / "note.txt").write_text("shared note")
                reader = TenantReadFile(root=scenario_dir, tenant=os.environ["PIRN_REPLAY_TENANT"])
                call = ToolCall(tool_name="read_file", arguments={"path": "note.txt"}, call_id="c1")
                ToolInvocation(tool=reader, call=call, _config=KnotConfig(id="invoke"))
            elif scenario == "factory_class":
                scaled = make_scaled(10 if self._mode == "record" else 1000)
                call = ToolCall(
                    tool_name="calculator", arguments={"expression": "2+3"}, call_id="c1"
                )
                ToolInvocation(tool=scaled, call=call, _config=KnotConfig(id="invoke"))
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
