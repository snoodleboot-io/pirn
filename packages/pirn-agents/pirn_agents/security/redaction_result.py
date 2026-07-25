"""``RedactionResult`` — the redacted value plus what was found.

A frozen pairing of the redacted ``value`` (a string, or a structurally-copied
mapping/sequence with secrets scrubbed) and the tuple of
:class:`~pirn_agents.security.secret_finding.SecretFinding`s describing every
redaction. ``leaked`` is a convenience for "were any secrets present?".
"""

from __future__ import annotations

from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.security.secret_finding import SecretFinding


class RedactionResult(PirnOpaqueValue):
    """Immutable result of a redaction pass over text or a structure."""

    def __init__(self, *, value: Any, findings: tuple[SecretFinding, ...]) -> None:
        """Store the redacted value and its findings.

        Args:
            value: The redacted value (secrets replaced with the placeholder).
            findings: The secret findings detected during redaction.

        Raises:
            TypeError: If ``findings`` is not a tuple of :class:`SecretFinding`.
        """
        if not isinstance(findings, tuple) or any(
            not isinstance(item, SecretFinding) for item in findings
        ):
            raise TypeError("RedactionResult: findings must be a tuple of SecretFinding")
        self._value = value
        self._findings = findings

    @property
    def value(self) -> Any:
        """Return the redacted value."""
        return self._value

    @property
    def findings(self) -> tuple[SecretFinding, ...]:
        """Return the tuple of secret findings."""
        return self._findings

    @property
    def leaked(self) -> bool:
        """Return whether any secret was detected."""
        return bool(self._findings)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return a stable content-addressing view (findings only, never the value)."""
        return {"findings": [finding._pirn_audit_dict() for finding in self._findings]}
