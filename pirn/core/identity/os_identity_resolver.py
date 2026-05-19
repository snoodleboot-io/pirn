from __future__ import annotations

import getpass

from pirn.core.identity.identity_resolver import IdentityResolver


class OsIdentityResolver(IdentityResolver):
    """Resolves identity from the operating system user running the process."""

    def resolve(self) -> str | None:
        return getpass.getuser()
