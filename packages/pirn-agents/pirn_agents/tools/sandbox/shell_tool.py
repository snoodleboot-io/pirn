"""``ShellTool`` — run a shell command in the opt-in sandbox executor."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pydantic import Field

from pirn_agents.tools.sandbox.sandbox_executor import SandboxExecutor
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_permissions import ToolPermissions


class ShellTool(Tool):
    """Execute a shell command in a sandbox and return stdout/stderr (opt-in)."""

    tool_name: ClassVar[str] = "shell"
    permissions: ClassVar[ToolPermissions] = ToolPermissions(mutating=True)

    def __init__(
        self,
        *,
        command: Knot | str,
        executor: Knot | SandboxExecutor,
        shell_path: Knot | str = "/bin/sh",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            command=command, executor=executor, shell_path=shell_path, _config=_config, **kwargs
        )

    async def process(
        self,
        command: Annotated[str, Field(description="The shell command line to run.")],
        executor: SandboxExecutor,
        shell_path: str = "/bin/sh",
        **_: Any,
    ) -> Mapping[str, Any]:
        """Run ``command`` through the sandbox and return its result.

        Args:
            command: The shell command line to run.
            executor: The :class:`SandboxExecutor` that gates and runs the
                command; bound once with ``ShellTool.bind(executor=...)``.
            shell_path: Path to the shell interpreter; defaults to ``/bin/sh``.

        Returns:
            The :class:`SandboxResult` mapping (stdout/stderr/exit_code/...).

        Raises:
            ValueError: If ``command`` is empty.
            SandboxDisabledError: If the sandbox is not opted in.
        """
        if not command:
            raise ValueError("shell: 'command' must be a non-empty string")
        result = await executor.execute(command=[shell_path, "-c", command])
        return result.as_mapping()
