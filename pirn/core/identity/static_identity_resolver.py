from __future__ import annotations

from pirn.core.identity.identity_resolver import IdentityResolver


class StaticIdentityResolver(IdentityResolver):
    """Resolves identity to a fixed string unconditionally.

    Useful for services and CI jobs that always run under a known account.
    """

    def __init__(self, actor: str) -> None:
        self._actor = actor

    def resolve(self) -> str | None:
        return self._actor
