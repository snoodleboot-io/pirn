"""Every agents exception WS2 touched actually subclasses PirnError at runtime.

Complements ``tests/test_core_vocabulary_ratchet.py`` (a static AST walk) with
a real ``issubclass`` check, and keeps each fixed root's previous builtin
base working for any ``except <builtin>`` handler that already existed.
"""

from __future__ import annotations

import pytest
from pirn.exceptions.pirn_error import PirnError

from pirn_agents.exceptions.agent_cycle_error import AgentCycleError
from pirn_agents.exceptions.agent_depth_exceeded_error import AgentDepthExceededError
from pirn_agents.exceptions.agent_recursion_error import AgentRecursionError
from pirn_agents.exceptions.missing_cassette_entry_error import MissingCassetteEntryError
from pirn_agents.exceptions.sandbox_disabled_error import SandboxDisabledError
from pirn_agents.exceptions.tool_argument_validation_error import ToolArgumentValidationError
from pirn_agents.exceptions.tool_cancelled_error import ToolCancelledError
from pirn_agents.exceptions.tool_invocation_error import ToolInvocationError
from pirn_agents.exceptions.tool_not_found_error import ToolNotFoundError
from pirn_agents.exceptions.tool_timeout_error import ToolTimeoutError
from pirn_agents.exceptions.unsupported_modality_error import UnsupportedModalityError
from pirn_agents.security.injection_detected_error import InjectionDetectedError
from pirn_agents.security.injection_verdict import InjectionVerdict
from pirn_agents.security.mcp_trust_error import McpTrustError
from pirn_agents.security.untrusted_directive_error import UntrustedDirectiveError


@pytest.mark.parametrize(
    ("exc_type", "builtin_base"),
    [
        (ToolInvocationError, Exception),
        (AgentRecursionError, RuntimeError),
        (SandboxDisabledError, RuntimeError),
        (UnsupportedModalityError, ValueError),
        (MissingCassetteEntryError, LookupError),
        (InjectionDetectedError, Exception),
        (McpTrustError, Exception),
        (UntrustedDirectiveError, Exception),
        # Subclasses of a fixed root inherit PirnError transitively.
        (ToolCancelledError, ToolInvocationError),
        (ToolNotFoundError, ToolInvocationError),
        (ToolTimeoutError, ToolInvocationError),
        (ToolArgumentValidationError, ToolInvocationError),
        (AgentCycleError, AgentRecursionError),
        (AgentDepthExceededError, AgentRecursionError),
    ],
)
def test_roots_on_pirn_error_and_keeps_its_builtin_base(
    exc_type: type[BaseException], builtin_base: type[BaseException]
) -> None:
    assert issubclass(exc_type, PirnError), f"{exc_type.__name__} does not subclass PirnError"
    assert issubclass(exc_type, builtin_base), (
        f"{exc_type.__name__} lost its {builtin_base.__name__} base — an existing "
        f"except {builtin_base.__name__} handler would stop catching it"
    )


def test_except_pirn_error_catches_every_fixed_exception() -> None:
    for build in (
        lambda: ToolInvocationError("boom"),
        lambda: AgentRecursionError(),
        lambda: SandboxDisabledError(),
        lambda: UnsupportedModalityError("image", "text-only"),
        lambda: MissingCassetteEntryError("k", "llm"),
        lambda: InjectionDetectedError(
            InjectionVerdict(flagged=True, score=1.0, decided_by="heuristic", reason="x")
        ),
        lambda: McpTrustError("denied"),
        lambda: UntrustedDirectiveError("nope"),
    ):
        with pytest.raises(PirnError):
            raise build()
