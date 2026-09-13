"""``EndpointIdentity`` — the secret-free identity of an HTTP provider's base URL.

Content identity for an HTTP LLM provider (PIR-840) has to name *where* requests go
without ever copying a value that might be a secret into lineage. A base URL can
carry secrets in several places: userinfo (``user:password@host``), a query string
(``?api_key=…``, ``?access_token=…``, ``?X-Amz-Credential=…``) and, in principle, a
fragment. A denylist scrubber cannot know every parameter name a gateway uses, so
this class does the opposite: it keeps an **allowlist** of URL components (scheme,
host, port, path) and refuses outright, returning ``None``, when anything else is
present. The caller treats ``None`` as "stay identity-keyed".

The path is kept because it selects the API surface (``/v1`` versus ``/v2``, a
gateway route, a deployment). A secret embedded in the path itself cannot be told
apart from a route and is not detected.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit


class EndpointIdentity:
    """Reduce a base URL to scheme, host, port and path, or ``None`` if it is not safe to."""

    #: Schemes an HTTP provider can be pointed at. Anything else is not understood
    #: well enough to name.
    _schemes: tuple[str, ...] = ("http", "https")

    #: Characters whose presence means the URL carries more than the allowlist:
    #: ``?`` a query (even an empty one), ``#`` a fragment, ``@`` userinfo, and ``\``
    #: which some URL parsers treat as a path separator and others do not.
    _refused_characters: frozenset[str] = frozenset("?#@\\")

    @staticmethod
    def of(base_url: str) -> dict[str, Any] | None:
        """Return ``{scheme, host, port, path}`` for ``base_url``, or ``None``.

        Args:
            base_url: The provider's configured base URL.

        Returns:
            The scheme and host lowercased, the explicit port (``None`` when the URL
            does not give one) and the path with trailing slashes removed, matching
            how the provider joins it with its completions path. ``None`` when the
            URL has userinfo, a query string or a fragment, is not plain printable
            ASCII, is not ``http``/``https``, has no host, or has an invalid port.
        """
        if not EndpointIdentity._is_plain_ascii(base_url):
            return None
        if EndpointIdentity._refused_characters.intersection(base_url):
            return None
        try:
            parts = urlsplit(base_url)
            port = parts.port
        except ValueError:
            return None
        scheme = parts.scheme.lower()
        if scheme not in EndpointIdentity._schemes:
            return None
        if parts.username is not None or parts.password is not None:
            return None
        if parts.query or parts.fragment:
            return None
        host = parts.hostname
        if not host:
            return None
        return {
            "scheme": scheme,
            "host": host,
            "port": port,
            "path": parts.path.rstrip("/"),
        }

    @staticmethod
    def _is_plain_ascii(text: str) -> bool:
        """Return whether ``text`` is printable ASCII with no whitespace or controls.

        URL parsers disagree about stripping tabs, newlines and other controls, and
        about internationalised hosts, so any such URL is not named at all.
        """
        return all(0x21 <= ord(character) <= 0x7E for character in text)
