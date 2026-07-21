"""SSRF guard shared by the HTTP fetch tool and connectors.

The single implementation of the host-egress policy: the HTTP fetch tool, the
connectors, :class:`~pirn_agents.security.egress_policy.EgressPolicy`, and
:class:`pirn_agents.specializations.document_processing._document_source_reader._DocumentSourceReader`
all compose it. A URL's hostname is resolved and rejected when **any** returned
address lands on a private, loopback, link-local, reserved, or multicast range
(this also blocks the cloud metadata endpoint ``169.254.169.254``, which is
link-local). An optional host allow-list narrows further. The policy (allow-list,
private-range opt-out, DNS resolver) is held as constructor state; the resolver is
injectable so tests never touch the network.

Three properties this guard deliberately has (PIR-741):

* **Every** resolved address is classified, not just the first. ``gethostbyname``
  returns a single A record, so a host publishing both a public and a private
  address used to pass while the client might connect to the private one.
* IPv4 **and** IPv6 are classified. ``gethostbyname`` is IPv4-only, so v6 literals
  and AAAA-only hosts previously failed closed as "unresolvable" — secure, but it
  made every IPv6 destination unreachable and the diagnostic misleading.
  IPv4-mapped v6 (``::ffff:169.254.169.254``) is unmapped before classification so
  it cannot smuggle a v4 metadata address past the v6 predicates.
* It returns a :class:`VettedEndpoint` rather than a bare hostname, carrying the
  address that was actually checked.

**DNS rebinding is not yet closed.** Callers still hand the original URL to their
HTTP client, which re-resolves independently, so a short-TTL attacker record can
answer public here and private at connect time. ``VettedEndpoint`` supplies
everything needed to pin (address, ``Host``, TLS SNI), but wiring it through the
four call sites changes the shape of every outbound request and is tracked
separately. Until then this guard narrows rebinding — an attacker must now keep
*every* published record public at check time — rather than eliminating it.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Sequence
from urllib.parse import urlparse

from pirn_agents.security.security_guard import SecurityGuard
from pirn_agents.tools.web.vetted_endpoint import VettedEndpoint


class SsrfGuard(SecurityGuard):
    """Reject URLs whose host is non-public or outside an optional allow-list."""

    def __init__(
        self,
        *,
        allowed_hosts: tuple[str, ...] | None = None,
        allow_private: bool = False,
        resolver: Callable[[str], str | Sequence[str]] | None = None,
    ) -> None:
        """Configure the egress policy.

        Args:
            allowed_hosts: When set, a URL's hostname must be a member.
            allow_private: When ``True``, the private/loopback/link-local IP check
                is skipped (opt-in, for trusted internal endpoints only).
            resolver: Hostname→address resolver. May return a single address or a
                sequence of them; a sequence is preferred, since **all** returned
                addresses are classified and any non-public one rejects the host.
                Defaults to :meth:`_resolve_all`, which uses ``socket.getaddrinfo``
                and so covers both IPv4 and IPv6. Injected in tests so no real DNS
                lookup occurs.
        """
        self._allowed_hosts: tuple[str, ...] | None = allowed_hosts
        self._allow_private: bool = allow_private
        # Held as-is rather than defaulted here: binding ``_resolve_all`` at
        # construction would make a later patch of it silently fall through to real
        # DNS for any guard built in an ``__init__`` (HttpConnector, HttpRequestTool).
        self._resolver: Callable[[str], str | Sequence[str]] | None = resolver

    @staticmethod
    def _resolve_all(hostname: str) -> Sequence[str]:
        """Return every address ``hostname`` resolves to, across both families."""
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        # Dedupe while preserving order: a host commonly repeats an address per
        # socket type, and the first entry is the one we will pin to.
        seen: dict[str, None] = {}
        for info in infos:
            seen.setdefault(str(info[4][0]), None)
        return tuple(seen)

    @staticmethod
    def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        """Return whether ``ip`` is a routable public address."""
        # An IPv4-mapped v6 address (::ffff:a.b.c.d) carries a v4 address that the
        # v6 predicates do not classify, so unmap before deciding.
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        # Deprecated RFC 3879 site-local (fec0::/10) is reported as neither private
        # NOR non-global by ipaddress, so `is_global` alone lets it through. Still
        # live in older enterprise and appliance networks.
        if isinstance(ip, ipaddress.IPv6Address) and ip.is_site_local:
            return False
        # `is_global` additionally catches RFC 6598 carrier-grade NAT (100.64/10),
        # which none of the individual predicates below classify.
        return ip.is_global and not (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )

    def assert_public_host(self, url: str) -> VettedEndpoint:
        """Validate ``url``'s host and return the endpoint to connect to.

        Args:
            url: The absolute http(s) URL to vet.

        Returns:
            A :class:`VettedEndpoint` carrying the hostname and the vetted address.
            Callers should pin their request to it rather than re-resolving the
            original URL, which would reopen the DNS-rebinding window.

        Raises:
            ValueError: If the scheme is not http(s), the host is missing, is not
                in the configured ``allowed_hosts``, is unresolvable, or any
                resolved address is non-public.
        """
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            self._reject(f"http_request: only http(s) URLs are allowed, got {url!r}")
        hostname = parsed.hostname
        if not hostname:
            self._reject(f"http_request: URL has no hostname: {url!r}")
        if self._allowed_hosts is not None and hostname not in self._allowed_hosts:
            self._reject(f"http_request: host {hostname!r} not in allowed_hosts")
        port = parsed.port
        addresses = self._resolved_addresses(hostname)
        if self._allow_private:
            # Opt-out skips classification, but still pins to a resolved address so
            # the caller's request shape is identical either way.
            return VettedEndpoint(hostname=hostname, address=addresses[0], port=port)
        for candidate in addresses:
            try:
                ip = ipaddress.ip_address(candidate)
            except ValueError:
                self._reject(
                    f"http_request: refusing unparseable address for {hostname!r}: {candidate!r}"
                )
            if not self._is_public(ip):
                self._reject(
                    f"http_request: refusing private/loopback/link-local host: {hostname!r} -> {ip}"
                )
        return VettedEndpoint(hostname=hostname, address=addresses[0], port=port)

    def _resolved_addresses(self, hostname: str) -> tuple[str, ...]:
        """Resolve ``hostname`` to a non-empty tuple of addresses, or reject."""
        resolver = self._resolver if self._resolver is not None else self._resolve_all
        try:
            resolved = resolver(hostname)
        except (OSError, ValueError) as exc:
            raise ValueError(f"http_request: refusing unresolvable host: {hostname!r}") from exc
        # The seam accepts a single address for backwards compatibility with the
        # many injected resolvers already in the tree; normalise to a tuple.
        addresses = (resolved,) if isinstance(resolved, str) else tuple(resolved)
        if not addresses:
            self._reject(f"http_request: refusing unresolvable host: {hostname!r}")
        return addresses
