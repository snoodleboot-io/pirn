"""SSRF guard shared by the HTTP fetch tool and connectors.

Mirrors the hardening in
:class:`pirn_agents.specializations.document_processing._document_loader._DocumentLoader`:
a URL's hostname is resolved to an IP and rejected when it lands on a private,
loopback, link-local, reserved, or multicast range (this also blocks the cloud
metadata endpoint ``169.254.169.254``, which is link-local). An optional host
allow-list narrows further. The policy (allow-list, private-range opt-out, DNS
resolver) is held as constructor state; the resolver is injectable so tests never
touch the network.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlparse

from pirn_agents.security.security_guard import SecurityGuard


class SsrfGuard(SecurityGuard):
    """Reject URLs whose host is non-public or outside an optional allow-list."""

    def __init__(
        self,
        *,
        allowed_hosts: tuple[str, ...] | None = None,
        allow_private: bool = False,
        resolver: Callable[[str], str] | None = None,
    ) -> None:
        """Configure the egress policy.

        Args:
            allowed_hosts: When set, a URL's hostname must be a member.
            allow_private: When ``True``, the private/loopback/link-local IP check
                is skipped (opt-in, for trusted internal endpoints only).
            resolver: Hostname→IP resolver; defaults to
                :func:`socket.gethostbyname`. Injected in tests so no real DNS
                lookup occurs.
        """
        self._allowed_hosts: tuple[str, ...] | None = allowed_hosts
        self._allow_private: bool = allow_private
        self._resolver: Callable[[str], str] = (
            resolver if resolver is not None else socket.gethostbyname
        )

    def assert_public_host(self, url: str) -> str:
        """Validate ``url``'s host and return its hostname, or raise on an SSRF risk.

        Args:
            url: The absolute http(s) URL to vet.

        Returns:
            The validated hostname.

        Raises:
            ValueError: If the scheme is not http(s), the host is missing, is not
                in the configured ``allowed_hosts``, is unresolvable, or resolves
                to a non-public IP.
        """
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            self._reject(f"http_request: only http(s) URLs are allowed, got {url!r}")
        hostname = parsed.hostname
        if not hostname:
            self._reject(f"http_request: URL has no hostname: {url!r}")
        if self._allowed_hosts is not None and hostname not in self._allowed_hosts:
            self._reject(f"http_request: host {hostname!r} not in allowed_hosts")
        if self._allow_private:
            return hostname
        try:
            ip = ipaddress.ip_address(self._resolver(hostname))
        except (OSError, ValueError) as exc:
            raise ValueError(f"http_request: refusing unresolvable host: {hostname!r}") from exc
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            self._reject(
                f"http_request: refusing private/loopback/link-local host: {hostname!r} -> {ip}"
            )
        return hostname
