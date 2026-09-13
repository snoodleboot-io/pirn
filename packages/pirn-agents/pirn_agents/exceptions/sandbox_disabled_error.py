"""``SandboxDisabledError`` — raised when a sandbox tool is used while disabled."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class SandboxDisabledError(PirnError, RuntimeError):
    """Raised when ``python_exec``/``shell`` is invoked but the sandbox is off.

    Subclasses :class:`~pirn.exceptions.pirn_error.PirnError` in addition to
    ``RuntimeError`` so every existing ``except RuntimeError`` handler keeps
    working unchanged, while new code can narrow to ``PirnError``.

    The sandbox executor is **opt-in and disabled by default** (OD-1). Invoking a
    tool backed by a disabled :class:`~pirn_agents.tools.sandbox.sandbox_executor.SandboxExecutor`
    raises this error rather than silently executing anything.
    """
