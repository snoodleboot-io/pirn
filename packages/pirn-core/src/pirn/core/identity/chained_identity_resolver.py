from __future__ import annotations

from pirn.core.identity.identity_resolver import IdentityResolver


class ChainedIdentityResolver(IdentityResolver):
    """Tries each resolver in order, returning the first non-None result.

    Returns ``None`` only if all resolvers in the chain return ``None``.
    """

    def __init__(self, resolvers: list[IdentityResolver]) -> None:
        self._resolvers = resolvers

    def resolve(self) -> str | None:
        for resolver in self._resolvers:
            result = resolver.resolve()
            if result is not None:
                return result
        return None
