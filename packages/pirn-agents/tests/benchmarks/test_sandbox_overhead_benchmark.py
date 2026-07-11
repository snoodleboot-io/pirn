"""Sandbox-overhead micro-benchmark (PIR-219).

Marked ``@pytest.mark.benchmark``. Compares the wall-clock cost of running a
trivial command through :class:`SandboxExecutor` + :class:`SubprocessSandboxBackend`
against a raw :func:`asyncio.create_subprocess_exec` call, to quantify the
timeout/guard overhead the sandbox adds. Measured directly with
:func:`time.perf_counter`; no plugin dependency.
"""

from __future__ import annotations

import asyncio
import sys
import time

import pytest

from pirn_agents.tools.sandbox.sandbox_executor import SandboxExecutor
from pirn_agents.tools.sandbox.subprocess_sandbox_backend import SubprocessSandboxBackend


async def _raw_call() -> None:
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "pass",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


@pytest.mark.benchmark
async def test_sandbox_overhead_is_bounded() -> None:
    iterations = 5
    executor = SandboxExecutor(enabled=True, backend=SubprocessSandboxBackend())

    start = time.perf_counter()
    for _ in range(iterations):
        await _raw_call()
    raw_elapsed = (time.perf_counter() - start) / iterations

    start = time.perf_counter()
    for _ in range(iterations):
        await executor.execute(command=[sys.executable, "-c", "pass"])
    sandbox_elapsed = (time.perf_counter() - start) / iterations

    # The sandbox wraps the same subprocess spawn; overhead must stay modest
    # (loose bound to avoid flakiness on a busy CI host).
    assert sandbox_elapsed < raw_elapsed * 5 + 0.05
    print(
        f"[benchmark] sandbox_overhead raw={raw_elapsed:.4g} "
        f"sandbox={sandbox_elapsed:.4g} ratio={sandbox_elapsed / raw_elapsed:.3g}"
    )
