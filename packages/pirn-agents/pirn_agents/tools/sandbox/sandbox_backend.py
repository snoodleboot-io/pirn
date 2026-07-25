"""``SandboxBackend`` — injectable interface for executing sandboxed commands.

The :class:`~pirn_agents.tools.sandbox.sandbox_executor.SandboxExecutor` delegates
to a :class:`SandboxBackend`, so the execution mechanism is swappable — the
default subprocess backend for local use, or a stronger container/VM backend a
deployment injects. Backends receive an already-built argv command plus the
hard timeout and output cap to enforce.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.tools.sandbox.sandbox_result import SandboxResult


class SandboxBackend(PirnOpaqueValue):
    """Interface every sandbox execution backend must satisfy."""

    async def run(
        self,
        *,
        command: Sequence[str],
        stdin: str | None,
        timeout: float,
        max_output_bytes: int,
    ) -> SandboxResult:
        """Execute ``command`` under a hard ``timeout`` and output cap.

        Implementations must kill the process (and any children) when ``timeout``
        elapses and must truncate captured output at ``max_output_bytes``.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement run()")
