"""``SandboxDisabledError`` — raised when a sandbox tool is used while disabled."""

from __future__ import annotations


class SandboxDisabledError(RuntimeError):
    """Raised when ``python_exec``/``shell`` is invoked but the sandbox is off.

    The sandbox executor is **opt-in and disabled by default** (OD-1). Invoking a
    tool backed by a disabled :class:`~pirn_agents.tools.sandbox.sandbox_executor.SandboxExecutor`
    raises this error rather than silently executing anything.
    """
