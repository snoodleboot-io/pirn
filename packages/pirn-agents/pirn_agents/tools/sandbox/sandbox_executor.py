"""``SandboxExecutor`` — opt-in, timeout-bounded execution front-end (OD-1).

Resolves open design question OD-1: sandboxed code/command execution is provided
but is **disabled by default**. A :class:`SandboxExecutor` only runs anything when
constructed with ``enabled=True``; otherwise :meth:`execute` raises
:class:`~pirn_agents.exceptions.sandbox_disabled_error.SandboxDisabledError`. The
execution mechanism is an injectable :class:`SandboxBackend` (default:
:class:`SubprocessSandboxBackend`), and a hard timeout plus output cap are applied
to every run.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.exceptions.sandbox_disabled_error import SandboxDisabledError
from pirn_agents.tools.sandbox.sandbox_backend import SandboxBackend
from pirn_agents.tools.sandbox.sandbox_result import SandboxResult
from pirn_agents.tools.sandbox.subprocess_sandbox_backend import SubprocessSandboxBackend


class SandboxExecutor(PirnOpaqueValue):
    """Gate and run sandboxed commands, disabled unless explicitly opted into."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        backend: SandboxBackend | None = None,
        timeout: float = 5.0,
        max_output_bytes: int = 65_536,
    ) -> None:
        """Configure the executor's opt-in flag, backend, and limits.

        Args:
            enabled: Master switch; when ``False`` (default) every :meth:`execute`
                call raises :class:`SandboxDisabledError`.
            backend: Execution backend; defaults to :class:`SubprocessSandboxBackend`.
            timeout: Hard per-execution timeout in seconds.
            max_output_bytes: Output cap applied to stdout and stderr.

        Raises:
            TypeError: If ``backend`` is provided but is not a :class:`SandboxBackend`.
            ValueError: If ``timeout`` or ``max_output_bytes`` is not positive.
        """
        if backend is not None and not isinstance(backend, SandboxBackend):
            raise TypeError(
                f"SandboxExecutor: backend must be a SandboxBackend, got {type(backend).__name__}"
            )
        if timeout <= 0:
            raise ValueError(f"SandboxExecutor: timeout must be positive, got {timeout}")
        if max_output_bytes <= 0:
            raise ValueError(
                f"SandboxExecutor: max_output_bytes must be positive, got {max_output_bytes}"
            )
        self._enabled = enabled
        self._backend = backend if backend is not None else SubprocessSandboxBackend()
        self._timeout = timeout
        self._max_output_bytes = max_output_bytes

    @property
    def enabled(self) -> bool:
        """Return whether execution is opted into."""
        return self._enabled

    async def execute(self, *, command: Sequence[str], stdin: str | None = None) -> SandboxResult:
        """Run ``command`` through the backend, enforcing the opt-in flag.

        Args:
            command: The argv sequence to execute.
            stdin: Optional text piped to the process's standard input.

        Returns:
            The :class:`SandboxResult` of the run.

        Raises:
            SandboxDisabledError: If the executor was not constructed with
                ``enabled=True``.
            ValueError: If ``command`` is not a non-empty sequence of strings.
        """
        if not self._enabled:
            raise SandboxDisabledError(
                "SandboxExecutor is disabled; construct it with enabled=True to opt in (OD-1)."
            )
        command_list = list(command)
        if not command_list or not all(isinstance(part, str) for part in command_list):
            raise ValueError("SandboxExecutor: command must be a non-empty sequence of strings")
        return await self._backend.run(
            command=command_list,
            stdin=stdin,
            timeout=self._timeout,
            max_output_bytes=self._max_output_bytes,
        )
