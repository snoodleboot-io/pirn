"""Sandbox toolset — opt-in, timeout-bounded ``python_exec``/``shell`` execution.

Disabled by default (OD-1). Nothing here runs untrusted code unless a
:class:`~pirn_agents.tools.sandbox.sandbox_executor.SandboxExecutor` is explicitly
constructed with ``enabled=True``.
"""

from __future__ import annotations
