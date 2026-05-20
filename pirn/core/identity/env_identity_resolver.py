from __future__ import annotations

import os

from pirn.core.identity.identity_resolver import IdentityResolver


class EnvIdentityResolver(IdentityResolver):
    """Resolves identity from environment variables.

    Iterates *vars* in order and returns the first non-empty value found.
    Returns ``None`` if none of the variables are set or non-empty.
    """

    def __init__(
        self,
        vars: list[str] | None = None,
    ) -> None:
        self._vars = (
            vars
            if vars is not None
            else [
                "GITHUB_ACTOR",
                "GITLAB_USER_LOGIN",
                "CI_USER",
                "BUILD_USER",
            ]
        )

    def resolve(self) -> str | None:
        for var in self._vars:
            value = os.environ.get(var, "").strip()
            if value:
                return value
        return None
