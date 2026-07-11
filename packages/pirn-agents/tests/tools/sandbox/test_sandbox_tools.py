"""Security tests for the sandbox executor and python_exec/shell tools (PIR-167).

Covers the default-off opt-in gate (disabled → error), deterministic behaviour
against a stub backend, and real timeout enforcement + output truncation with the
subprocess backend (a sleeping child is killed; oversized output is cut).
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

import pytest

from pirn_agents.exceptions.sandbox_disabled_error import SandboxDisabledError
from pirn_agents.tools.sandbox.python_exec_tool import PythonExecTool
from pirn_agents.tools.sandbox.sandbox_backend import SandboxBackend
from pirn_agents.tools.sandbox.sandbox_executor import SandboxExecutor
from pirn_agents.tools.sandbox.sandbox_result import SandboxResult
from pirn_agents.tools.sandbox.shell_tool import ShellTool
from pirn_agents.tools.sandbox.subprocess_sandbox_backend import SubprocessSandboxBackend
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_status import ToolStatus


class _StubSandboxBackend(SandboxBackend):
    def __init__(self, result: SandboxResult) -> None:
        self._result = result
        self.calls: list[tuple[Sequence[str], str | None, float, int]] = []

    async def run(
        self,
        *,
        command: Sequence[str],
        stdin: str | None,
        timeout: float,
        max_output_bytes: int,
    ) -> SandboxResult:
        self.calls.append((list(command), stdin, timeout, max_output_bytes))
        return self._result


def _ok_result(stdout: str = "ok") -> SandboxResult:
    return SandboxResult(stdout=stdout, stderr="", exit_code=0, timed_out=False, truncated=False)


class TestOptInGate:
    async def test_executor_disabled_by_default(self) -> None:
        executor = SandboxExecutor()
        assert executor.enabled is False
        with pytest.raises(SandboxDisabledError):
            await executor.execute(command=["echo", "hi"])

    async def test_python_exec_disabled_yields_error_result(self) -> None:
        tool = PythonExecTool(executor=SandboxExecutor())
        call = ToolCall(tool_name="python_exec", arguments={"code": "print(1)"}, call_id="c")
        outcome = await tool.as_tool_result(call)
        assert outcome.status is ToolStatus.ERROR
        assert "disabled" in (outcome.error or "")

    async def test_shell_disabled_raises(self) -> None:
        tool = ShellTool(executor=SandboxExecutor())
        with pytest.raises(SandboxDisabledError):
            await tool.invoke({"command": "echo hi"})


class TestWithStubBackend:
    async def test_python_exec_runs_when_enabled(self) -> None:
        backend = _StubSandboxBackend(_ok_result("hello"))
        executor = SandboxExecutor(enabled=True, backend=backend)
        tool = PythonExecTool(executor=executor, python_executable="/usr/bin/python3")
        result = await tool.invoke({"code": "print('hello')"})
        assert result["stdout"] == "hello"
        assert result["exit_code"] == 0
        # code is delivered on stdin; interpreter run with isolated flags
        assert backend.calls[0][0] == ["/usr/bin/python3", "-I", "-"]
        assert backend.calls[0][1] == "print('hello')"

    async def test_shell_builds_dash_c_command(self) -> None:
        backend = _StubSandboxBackend(_ok_result())
        tool = ShellTool(
            executor=SandboxExecutor(enabled=True, backend=backend), shell_path="/bin/sh"
        )
        await tool.invoke({"command": "echo hi"})
        assert backend.calls[0][0] == ["/bin/sh", "-c", "echo hi"]

    async def test_timeout_flag_surfaces_as_result(self) -> None:
        timed_out = SandboxResult(
            stdout="", stderr="", exit_code=None, timed_out=True, truncated=False
        )
        tool = ShellTool(
            executor=SandboxExecutor(enabled=True, backend=_StubSandboxBackend(timed_out))
        )
        result = await tool.invoke({"command": "sleep 100"})
        assert result["timed_out"] is True
        assert result["exit_code"] is None

    def test_executor_rejects_bad_backend(self) -> None:
        with pytest.raises(TypeError):
            SandboxExecutor(enabled=True, backend=object())  # type: ignore[arg-type]

    async def test_executor_rejects_empty_command(self) -> None:
        executor = SandboxExecutor(enabled=True, backend=_StubSandboxBackend(_ok_result()))
        with pytest.raises(ValueError):
            await executor.execute(command=[])


class TestSubprocessBackendReal:
    async def test_captures_stdout(self) -> None:
        executor = SandboxExecutor(enabled=True, backend=SubprocessSandboxBackend())
        tool = PythonExecTool(executor=executor)
        result = await tool.invoke({"code": "print('from-sandbox')"})
        assert result["exit_code"] == 0
        assert "from-sandbox" in result["stdout"]
        assert result["timed_out"] is False

    async def test_timeout_kills_long_running_process(self) -> None:
        executor = SandboxExecutor(enabled=True, backend=SubprocessSandboxBackend(), timeout=0.3)
        tool = PythonExecTool(executor=executor)
        result = await tool.invoke({"code": "import time; time.sleep(30)"})
        assert result["timed_out"] is True
        assert result["exit_code"] is None

    async def test_output_truncation(self) -> None:
        executor = SandboxExecutor(
            enabled=True, backend=SubprocessSandboxBackend(), max_output_bytes=100
        )
        result = await executor.execute(command=[sys.executable, "-c", "print('x' * 5000)"])
        assert result.truncated is True
        assert len(result.stdout) <= 100

    async def test_nonzero_exit_code(self) -> None:
        executor = SandboxExecutor(enabled=True, backend=SubprocessSandboxBackend())
        result = await executor.execute(command=[sys.executable, "-c", "import sys; sys.exit(3)"])
        assert result.exit_code == 3
        assert result.timed_out is False
