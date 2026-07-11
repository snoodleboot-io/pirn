"""``ShellTool`` — run a shell command in the opt-in sandbox executor."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.tools.base_tool import BaseTool
from pirn_agents.tools.sandbox.sandbox_executor import SandboxExecutor


class ShellTool(BaseTool):
    """Execute a shell command via a :class:`SandboxExecutor` (disabled by default)."""

    def __init__(self, *, executor: SandboxExecutor, shell_path: str = "/bin/sh") -> None:
        """Bind the tool to a sandbox executor and the shell to run.

        Args:
            executor: The :class:`SandboxExecutor` that gates and runs the command.
            shell_path: Path to the shell interpreter; defaults to ``/bin/sh``.

        Raises:
            TypeError: If ``executor`` is not a :class:`SandboxExecutor`.
        """
        if not isinstance(executor, SandboxExecutor):
            raise TypeError(
                f"shell: executor must be a SandboxExecutor, got {type(executor).__name__}"
            )
        self._executor = executor
        self._shell = shell_path

    @property
    def name(self) -> str:
        """Return the stable tool identifier ``"shell"``."""
        return "shell"

    @property
    def description(self) -> str:
        """Return the human-readable description shown to the planner."""
        return "Execute a shell command in a sandbox and return stdout/stderr (opt-in)."

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """Return the JSON Schema for the ``command`` argument."""
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command line to run."}
            },
            "required": ["command"],
        }

    async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Run the ``command`` argument through the sandbox and return its result.

        Returns:
            The :class:`SandboxResult` mapping (stdout/stderr/exit_code/…).

        Raises:
            TypeError: If ``arguments`` is not a mapping.
            ValueError: If ``command`` is missing/empty.
            SandboxDisabledError: If the sandbox is not opted in.
        """
        self._require_mapping(self.name, arguments)
        command = self._string_argument(self.name, arguments, "command")
        result = await self._executor.execute(command=[self._shell, "-c", command])
        return result.as_mapping()
