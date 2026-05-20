from __future__ import annotations

from pirn.core.identity.identity_resolver import IdentityResolver


class NullIdentityResolver(IdentityResolver):
    """Always returns None. Use in tests to suppress all identity resolution."""

    def resolve(self) -> str | None:
        return None
