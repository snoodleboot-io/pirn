"""DSN / connection-string credential scrubber.

Generalises the existing ``pirn/backends/postgres/_lazy_pool.py`` regex into
a reusable class. Used by :class:`pirn.domains.connectors.connection_config.ConnectionConfig`
to redact inline credentials from any DSN-style URL before logging.
"""

from __future__ import annotations

import re


class DsnScrubber:
    """Replace inline credentials in a DSN/URL with ``<redacted>``.

    Two redaction shapes are handled:

    1. ``postgres://user:password@host/db`` → ``postgres://<redacted>@host/db``
    2. ``https://host/path?api_key=abc&token=xyz`` → keys are redacted
       per-parameter.

    Idempotent — already-redacted strings round-trip unchanged. Safe on
    arbitrary input — non-DSN strings pass through.
    """

    _REDACTED = "<redacted>"

    def __init__(self) -> None:
        # Compile once per instance — avoids module-level state and lets
        # subclasses extend the rule set if needed.
        self._password_re = re.compile(r"(://)[^@/]+(@)")
        self._token_re = re.compile(
            r"(?i)([?&](?:password|token|api[-_]?key|secret|signature|sig|key)=)[^&]+"
        )

    def scrub(self, value: str) -> str:
        """Return ``value`` with inline credentials replaced by ``<redacted>``."""
        out = self._password_re.sub(rf"\1{self._REDACTED}\2", value)
        out = self._token_re.sub(rf"\1{self._REDACTED}", out)
        return out
