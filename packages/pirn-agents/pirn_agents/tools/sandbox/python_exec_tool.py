"""``PythonExecTool`` — run Python code in the opt-in sandbox executor."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from typing import Any

from pirn_agents.tools.base_tool import BaseTool
from pirn_agents.tools.sandbox.sandbox_executor import SandboxExecutor


class PythonExecTool(BaseTool):
    """Execute a Python snippet via a :class:`SandboxExecutor` (disabled by default)."""

    def __init__(self, *, executor: SandboxExecutor, python_executable: str | None = None) -> None:
        """Bind the tool to a sandbox executor and the interpreter to run.

        Args:
            executor: The :class:`SandboxExecutor` that gates and runs the code.
            python_executable: Interpreter path; defaults to the current one.

        Raises:
            TypeError: If ``executor`` is not a :class:`SandboxExecutor`.
        """
        if not isinstance(executor, SandboxExecutor):
            raise TypeError(
                f"python_exec: executor must be a SandboxExecutor, got {type(executor).__name__}"
            )
        self._executor = executor
        self._python = python_executable if python_executable is not None else sys.executable

    @property
    def name(self) -> str:
        """Return the stable tool identifier ``"python_exec"``."""
        return "python_exec"

    @property
    def description(self) -> str:
        """Return the human-readable description shown to the planner."""
        return "Execute a Python code snippet in a sandbox and return stdout/stderr (opt-in)."

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """Return the JSON Schema for the ``code`` argument."""
        return {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Python source to execute."}},
            "required": ["code"],
        }

    async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Run the ``code`` argument through the sandbox and return its result.

        Returns:
            The :class:`SandboxResult` mapping (stdout/stderr/exit_code/…).

        Raises:
            TypeError: If ``arguments`` is not a mapping.
            ValueError: If ``code`` is missing/empty.
            SandboxDisabledError: If the sandbox is not opted in.
        """
        self._require_mapping(self.name, arguments)
        code = self._string_argument(self.name, arguments, "code")
        result = await self._executor.execute(command=[self._python, "-I", "-"], stdin=code)
        return result.as_mapping()
