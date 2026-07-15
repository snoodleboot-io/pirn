"""``SecretRedactor`` — redact secrets in tool args, results, and log text.

Layers structured redaction on top of
:class:`~pirn_agents.security.secret_leak_scanner.SecretLeakScanner`: it walks a
tool's argument mapping or result value, redacting string leaves through the
scanner *and* blanking any value whose key name looks secret-bearing
(``password``, ``api_key``, ``authorization``, …) regardless of its format. The
walk returns a structurally-identical copy — the caller's original object is
never mutated — wrapped in a
:class:`~pirn_agents.security.redaction_result.RedactionResult`.

This is the "extend ``_clear_credentials`` to new surfaces" step: the same
redactor guards the previously-unprotected tool-arg, tool-result, and log
surfaces, complementing the connector ``_clear_credentials`` credential-drop.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents.security.redaction_result import RedactionResult
from pirn_agents.security.secret_finding import SecretFinding
from pirn_agents.security.secret_leak_scanner import SecretLeakScanner


class SecretRedactor:
    """Recursively redact secrets in structured tool args / results and text."""

    def __init__(
        self,
        *,
        scanner: SecretLeakScanner | None = None,
        secret_key_names: Sequence[str] | None = None,
        placeholder: str = "<redacted>",
    ) -> None:
        """Configure the redactor.

        Args:
            scanner: The text scanner to reuse; a default one is built when
                ``None``.
            secret_key_names: Override the set of key names whose values are
                always redacted; a sensible default set is used when ``None``.
            placeholder: Replacement token for key-name redactions.

        Raises:
            TypeError: If ``scanner`` is not a :class:`SecretLeakScanner`.
        """
        if scanner is not None and not isinstance(scanner, SecretLeakScanner):
            raise TypeError("SecretRedactor: scanner must be a SecretLeakScanner")
        self._scanner = scanner if scanner is not None else SecretLeakScanner()
        self._placeholder = placeholder
        raw = secret_key_names if secret_key_names is not None else self._default_key_names()
        self._secret_key_names = frozenset(self._normalise(name) for name in raw)

    @staticmethod
    def _default_key_names() -> tuple[str, ...]:
        """Return the default secret-bearing key names."""
        return (
            "password",
            "passwd",
            "pwd",
            "secret",
            "secretkey",
            "apikey",
            "accesskey",
            "accesstoken",
            "token",
            "authorization",
            "auth",
            "privatekey",
            "clientsecret",
            "dsn",
            "connectionstring",
        )

    @staticmethod
    def _normalise(name: str) -> str:
        """Lower-case ``name`` and drop non-alphanumeric characters."""
        return "".join(ch for ch in str(name).lower() if ch.isalnum())

    def redact_text(self, text: str) -> RedactionResult:
        """Redact secrets in a bare string.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        redacted, kinds = self._scanner.redact_text(text)
        findings = tuple(SecretFinding(kind=kind, path="text") for kind in kinds)
        return RedactionResult(value=redacted, findings=findings)

    def redact_arguments(self, arguments: Mapping[str, Any]) -> RedactionResult:
        """Redact secrets in a tool-call argument mapping.

        Raises:
            TypeError: If ``arguments`` is not a mapping.
        """
        if not isinstance(arguments, Mapping):
            raise TypeError(
                f"SecretRedactor: arguments must be a Mapping, got {type(arguments).__name__}"
            )
        findings: list[SecretFinding] = []
        value = self._redact(arguments, "args", findings)
        return RedactionResult(value=value, findings=tuple(findings))

    def redact_result(self, result: Any) -> RedactionResult:
        """Redact secrets in an arbitrary tool result value."""
        findings: list[SecretFinding] = []
        value = self._redact(result, "result", findings)
        return RedactionResult(value=value, findings=tuple(findings))

    def _redact(self, value: Any, path: str, findings: list[SecretFinding]) -> Any:
        """Recursively redact ``value``, appending findings with their ``path``."""
        if isinstance(value, Mapping):
            out: dict[Any, Any] = {}
            for key, item in value.items():
                child_path = f"{path}.{key}"
                if isinstance(key, str) and self._normalise(key) in self._secret_key_names:
                    out[key] = self._placeholder
                    findings.append(SecretFinding(kind="secret_key_name", path=child_path))
                else:
                    out[key] = self._redact(item, child_path, findings)
            return out
        if isinstance(value, str):
            redacted, kinds = self._scanner.redact_text(value)
            for kind in kinds:
                findings.append(SecretFinding(kind=kind, path=path))
            return redacted
        if isinstance(value, tuple):
            return tuple(
                self._redact(item, f"{path}[{index}]", findings) for index, item in enumerate(value)
            )
        if isinstance(value, list):
            return [
                self._redact(item, f"{path}[{index}]", findings) for index, item in enumerate(value)
            ]
        return value
