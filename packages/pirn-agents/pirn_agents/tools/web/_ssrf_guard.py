"""SSRF guard shared by the HTTP fetch tool.

Mirrors the hardening in
:class:`pirn_agents.specializations.document_processing._document_loader._DocumentLoader`:
a URL's hostname is resolved to an IP and rejected when it lands on a private,
loopback, link-local, reserved, or multicast range (this also blocks the cloud
metadata endpoint ``169.254.169.254``, which is link-local). An optional host
allow-list narrows further. The DNS resolver is injectable so tests never touch
the network.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlparse


def assert_public_host(
    url: str,
    *,
    allowed_hosts: tuple[str, ...] | None = None,
    allow_private: bool = False,
    resolver: Callable[[str], str] | None = None,
) -> str:
    """Validate ``url``'s host and return its hostname, or raise on an SSRF risk.

    Args:
        url: The absolute http(s) URL to vet.
        allowed_hosts: When set, the hostname must be a member.
        allow_private: When ``True``, the private/loopback/link-local IP check is
            skipped (opt-in, for trusted internal endpoints only).
        resolver: Hostname→IP resolver; defaults to :func:`socket.gethostbyname`.
            Injected in tests so no real DNS lookup occurs.

    Returns:
        The validated hostname.

    Raises:
        ValueError: If the scheme is not http(s), the host is missing, is not in
            ``allowed_hosts``, is unresolvable, or resolves to a non-public IP.
    """
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(f"http_request: only http(s) URLs are allowed, got {url!r}")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"http_request: URL has no hostname: {url!r}")
    if allowed_hosts is not None and hostname not in allowed_hosts:
        raise ValueError(f"http_request: host {hostname!r} not in allowed_hosts")
    if allow_private:
        return hostname
    resolve = resolver if resolver is not None else socket.gethostbyname
    try:
        ip = ipaddress.ip_address(resolve(hostname))
    except (OSError, ValueError) as exc:
        raise ValueError(f"http_request: refusing unresolvable host: {hostname!r}") from exc
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        raise ValueError(
            f"http_request: refusing private/loopback/link-local host: {hostname!r} -> {ip}"
        )
    return hostname
