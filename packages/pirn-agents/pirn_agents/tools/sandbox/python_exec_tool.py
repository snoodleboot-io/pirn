"""``PythonExecTool`` — run Python code in the opt-in sandbox executor."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from typing import Annotated, Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pydantic import Field

from pirn_agents.tools.sandbox.sandbox_executor import SandboxExecutor
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_permissions import ToolPermissions


class PythonExecTool(Tool):
    """Execute a Python code snippet in a sandbox and return stdout/stderr (opt-in)."""

    tool_name: ClassVar[str] = "python_exec"
    permissions: ClassVar[ToolPermissions] = ToolPermissions(mutating=True)

    def __init__(
        self,
        *,
        code: Knot | str,
        executor: Knot | SandboxExecutor,
        python_executable: Knot | str | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            code=code,
            executor=executor,
            python_executable=python_executable,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        code: Annotated[str, Field(description="Python source to execute.")],
        executor: SandboxExecutor,
        python_executable: str | None = None,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Run ``code`` through the sandbox and return its result.

        Args:
            code: The Python source to execute.
            executor: The :class:`SandboxExecutor` that gates and runs the
                code; bound once with ``PythonExecTool.bind(executor=...)``.
            python_executable: Interpreter path; defaults to the current one.

        Returns:
            The :class:`SandboxResult` mapping (stdout/stderr/exit_code/...).

        Raises:
            ValueError: If ``code`` is empty.
            SandboxDisabledError: If the sandbox is not opted in.
        """
        if not code:
            raise ValueError("python_exec: 'code' must be a non-empty string")
        python = python_executable if python_executable is not None else sys.executable
        result = await executor.execute(command=[python, "-I", "-"], stdin=code)
        return result.as_mapping()
