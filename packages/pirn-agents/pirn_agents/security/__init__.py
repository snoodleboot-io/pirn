"""Agentic security & trust primitives (F11 / PIR-24).

This package defends the agent's *tool / retrieval / MCP* attack surface — the
risks created by tool outputs, retrieved documents, and MCP-server responses
flowing back into the prompt as untrusted content. It complements
``pirn_agents.specializations.guardrails`` (which screens the user/model
boundary) with:

* untrusted-content wrapping + provenance tagging (S1),
* an :class:`~pirn_agents.security.injection_screen.InjectionScreen` gate (S2),
* tool-output sanitization + active-content quarantine (S3),
* an MCP-server trust policy + per-tool permission scopes (S4),
* an egress allow/deny policy + SSRF guard for HTTP tools (S5),
* secret-leak detection / redaction for tool args, results, and logs (S6).

Every primitive is a plain, backend-free class or :class:`PirnOpaqueValue`;
consumers import from the concrete module path rather than this package root.
"""

from __future__ import annotations

__all__: list[str] = []
