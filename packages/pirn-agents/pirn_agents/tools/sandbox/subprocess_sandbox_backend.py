"""``SubprocessSandboxBackend`` — default subprocess-based sandbox backend.

Runs the command in its own process session (``start_new_session=True``) so a
timeout can kill the whole process group — the child *and* anything it spawned —
via ``SIGKILL``. Output is captured and truncated at the configured cap.

Security boundary
-----------------
This backend provides **timeout and output containment only**. It does *not*
provide filesystem, network, or syscall isolation — a subprocess runs with the
host process's privileges. For untrusted code, inject a stronger backend
(container/VM/gVisor). See ``pirn_agents/TOOLS.md``. This is why the sandbox is
opt-in and disabled by default (OD-1).
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
from collections.abc import Sequence

from pirn_agents.tools.sandbox.sandbox_backend import SandboxBackend
from pirn_agents.tools.sandbox.sandbox_result import SandboxResult


class SubprocessSandboxBackend(SandboxBackend):
    """Execute a command in a timeout-bounded, output-capped subprocess."""

    async def run(
        self,
        *,
        command: Sequence[str],
        stdin: str | None,
        timeout: float,
        max_output_bytes: int,
    ) -> SandboxResult:
        """Run ``command``, killing the process group if it overruns ``timeout``.

        Returns:
            A :class:`SandboxResult`; ``timed_out`` is ``True`` and ``exit_code``
            is ``None`` when the hard timeout fired.
        """
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        payload = stdin.encode("utf-8") if stdin is not None else None
        try:
            async with asyncio.timeout(timeout):
                out, err = await proc.communicate(payload)
        except TimeoutError:
            self._kill_group(proc)
            with contextlib.suppress(Exception):
                await proc.wait()
            return SandboxResult(
                stdout="",
                stderr="",
                exit_code=None,
                timed_out=True,
                truncated=False,
            )
        truncated = len(out) > max_output_bytes or len(err) > max_output_bytes
        return SandboxResult(
            stdout=out[:max_output_bytes].decode("utf-8", errors="replace"),
            stderr=err[:max_output_bytes].decode("utf-8", errors="replace"),
            exit_code=proc.returncode,
            timed_out=False,
            truncated=truncated,
        )

    @staticmethod
    def _kill_group(proc: asyncio.subprocess.Process) -> None:
        """SIGKILL the child's whole process group, ignoring a vanished process."""
        if proc.pid is None:
            return
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
