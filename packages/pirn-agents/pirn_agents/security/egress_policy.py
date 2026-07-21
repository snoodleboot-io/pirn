"""``EgressPolicy`` — per-tool egress allow/deny-list + SSRF guard.

``EgressPolicy`` is F11's richer network-egress control. It is a callable
``(url) -> None`` — exactly the shape of the ``egress_policy`` seam already
exposed by the F16
:class:`~pirn_agents.connectors.http_connector.HttpConnector` — so it drops in
with **no change to the connector**: ``HttpConnector(egress_policy=EgressPolicy(...))``.

On each call it applies, in order:

1. **Deny-list** — an explicit block-list of hosts, checked first so a denied
   host can never be re-allowed.
2. **Allow-list + SSRF guard** — delegated to the F6
   :meth:`~pirn_agents.tools.web._ssrf_guard.SsrfGuard.assert_public_host`, which enforces
   an http(s) scheme, an optional host allow-list, and (unless ``allow_private``)
   rejects private / loopback / link-local / reserved / multicast IPs — including
   the cloud metadata endpoint ``169.254.169.254``.

The DNS resolver is injectable, so the same policy is fully offline-testable and
wires identically into the connector and the ``http_request`` tool.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from urllib.parse import urlparse

from pirn_agents.security.egress_error import EgressError
from pirn_agents.tools.web._ssrf_guard import SsrfGuard
from pirn_agents.tools.web.vetted_endpoint import VettedEndpoint


class EgressPolicy:
    """A callable egress guard: deny-list, then allow-list + SSRF/private-range block."""

    def __init__(
        self,
        *,
        allowed_hosts: Sequence[str] | None = None,
        denied_hosts: Sequence[str] = (),
        allow_private: bool = False,
        resolver: Callable[[str], str | Sequence[str]] | None = None,
    ) -> None:
        """Configure the egress lists and SSRF behaviour.

        Args:
            allowed_hosts: When set, only these hostnames may be reached.
            denied_hosts: Hostnames blocked outright (checked before the
                allow-list).
            allow_private: When ``True``, skip the private/loopback/link-local
                IP guard (opt-in, for trusted internal endpoints only).
            resolver: Optional hostname→IP resolver forwarded to the SSRF guard;
                injected in tests so no real DNS lookup occurs.

        Raises:
            TypeError: If ``allowed_hosts`` / ``denied_hosts`` are not sequences
                of strings.
        """
        allowed = self._freeze_hosts("allowed_hosts", allowed_hosts, optional=True)
        denied = self._freeze_hosts("denied_hosts", denied_hosts, optional=False)
        self._denied_hosts: frozenset[str] = denied if denied is not None else frozenset()
        self._ssrf = SsrfGuard(
            allowed_hosts=tuple(allowed) if allowed is not None else None,
            allow_private=allow_private,
            resolver=resolver,
        )

    @staticmethod
    def _freeze_hosts(
        label: str, hosts: Sequence[str] | None, *, optional: bool
    ) -> frozenset[str] | None:
        """Validate and freeze a host sequence into a set (or ``None``)."""
        if hosts is None:
            if optional:
                return None
            return frozenset()
        if isinstance(hosts, str) or not isinstance(hosts, Sequence):
            raise TypeError(f"EgressPolicy: {label} must be a sequence of hostnames or None")
        return frozenset(str(host) for host in hosts)

    def __call__(self, url: str) -> VettedEndpoint:
        """Vet ``url`` for egress, raising :class:`EgressError` when blocked.

        Args:
            url: The absolute http(s) URL about to be requested.

        Returns:
            The :class:`VettedEndpoint` for the approved host. Callers should pin
            their request to it rather than re-resolving the original URL, which
            would reopen the DNS-rebinding window (PIR-746).

        Raises:
            EgressError: If the host is deny-listed, not allow-listed, uses a
                non-http(s) scheme, or resolves to a private/SSRF range.
        """
        host = urlparse(url).hostname
        if host is not None and host in self._denied_hosts:
            raise EgressError(f"EgressPolicy: host {host!r} is deny-listed", host=host)
        try:
            return self._ssrf.assert_public_host(url)
        except ValueError as exc:
            raise EgressError(str(exc), host=host) from exc

    def is_allowed(self, url: str) -> bool:
        """Return whether ``url`` passes the policy (never raises)."""
        try:
            self(url)
        except EgressError:
            return False
        return True
