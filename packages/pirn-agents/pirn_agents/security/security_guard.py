"""``SecurityGuard`` — shared base for injectable security-policy guards.

A guard vets one operation's inputs against a fixed policy and raises
:class:`ValueError` on a violation. Subclasses hold their policy configuration
(a root directory, an allow-list, a forbidden-keyword set) as constructor state
— computed once, not rebuilt per call — and expose a domain-specific check
(:meth:`ReadOnlySqlGuard.assert_read_only`, :meth:`PathGuard.resolve`,
:meth:`SsrfGuard.assert_public_host`). Tools inject a guard instance rather than
calling a module free function, so the policy is a substitutable dependency
(DIP) and a test can supply a guard configured for the case under test.

The base centralises the rejection path so every guard raises the same
exception type with a caller-facing message.
"""

from __future__ import annotations

from typing import NoReturn


class SecurityGuard:
    """Base for a policy guard that vets inputs and rejects violations."""

    def _reject(self, message: str) -> NoReturn:
        """Raise a :class:`ValueError` carrying ``message`` (the policy violation)."""
        raise ValueError(message)
