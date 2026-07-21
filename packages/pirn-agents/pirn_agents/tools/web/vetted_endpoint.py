"""``VettedEndpoint`` — a host that passed the SSRF guard, pinned to its address.

:class:`~pirn_agents.tools.web._ssrf_guard.SsrfGuard` resolves a hostname and
classifies every address it returns. Handing the *original URL* to an HTTP client
afterwards throws that work away: the client re-resolves independently, so a
short-TTL attacker record can answer public at check time and private at connect
time (DNS rebinding). ``VettedEndpoint`` carries the address that was actually
vetted, so the caller connects to *that* and the check cannot be raced.

Pinning rewrites the URL host to the vetted IP and restores the original hostname
through the ``Host`` header and the TLS ``sni_hostname`` extension, so virtual
hosting and certificate verification still see the real name — only the address
resolution is bypassed.

Internal API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class VettedEndpoint(PirnOpaqueValue):
    """A hostname that passed the guard, plus the address it resolved to.

    Attributes
    ----------
    hostname:
        The original hostname from the URL, preserved for ``Host`` and SNI.
    address:
        One address that passed classification. Every address the resolver
        returned was checked; this is the one to connect to.
    port:
        The explicit port from the URL, or ``None`` when the scheme default applies.
    """

    hostname: str
    address: str
    port: int | None = None

    @property
    def _bracketed_address(self) -> str:
        """IPv6 literals need brackets inside a URL authority."""
        return f"[{self.address}]" if ":" in self.address else self.address

    @property
    def host_header(self) -> str:
        """The ``Host`` value preserving the original name and explicit port."""
        return f"{self.hostname}:{self.port}" if self.port is not None else self.hostname

    def pinned_url(self, url: str) -> str:
        """Return ``url`` with its host replaced by the vetted address.

        Path, query, fragment and any explicit port are preserved; only the host
        component changes, so the request targets the address that was checked.
        """
        parsed = urlparse(url)
        if parsed.hostname != self.hostname:
            raise ValueError(
                f"VettedEndpoint: refusing to pin {url!r} — vetted host is "
                f"{self.hostname!r}, URL host is {parsed.hostname!r}"
            )
        netloc = self._bracketed_address
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
        if parsed.username:
            credentials = parsed.username
            if parsed.password:
                credentials = f"{credentials}:{parsed.password}"
            netloc = f"{credentials}@{netloc}"
        return urlunparse(parsed._replace(netloc=netloc))

    def request_headers(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        """Merge ``Host`` into ``headers`` so the origin still sees the real name."""
        merged = dict(headers) if headers else {}
        merged["Host"] = self.host_header
        return merged

    @property
    def request_extensions(self) -> dict[str, Any]:
        """httpx/httpcore extensions pinning TLS SNI to the original hostname.

        Without this the handshake would send the IP literal as SNI and verify the
        certificate against it, so every HTTPS request to a pinned address would
        fail verification.
        """
        return {"sni_hostname": self.hostname}

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"hostname": self.hostname, "address": self.address, "port": self.port}
