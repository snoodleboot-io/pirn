"""Tests for the egress policy + SSRF guard (PIR-267 / PIR-324, PIR-326, PIR-329).

Covers allowed hosts, denied hosts, allow-list misses, and private-range / SSRF
attempts. The DNS resolver is injected so every check is offline. The cross-layer
"seam closure" tests — wiring the same policy into the agents ``HttpConnector`` and
``http_request`` tool — live in the pirn-agents suite, since core must not import
the agents layer.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from pirn.security.egress_error import EgressError
from pirn.security.egress_policy import EgressPolicy


def _resolver(mapping: Mapping[str, str]) -> Any:
    """Return a DNS resolver stub backed by ``mapping`` (host -> IP)."""

    def _resolve(host: str) -> str:
        return mapping[host]

    return _resolve


def test_allowed_public_host_passes() -> None:
    policy = EgressPolicy(resolver=_resolver({"api.example.com": "93.184.216.34"}))
    policy("https://api.example.com/data")  # does not raise
    assert policy.is_allowed("https://api.example.com/data")


def test_denied_host_blocked_first() -> None:
    policy = EgressPolicy(
        denied_hosts=("evil.example",),
        resolver=_resolver({"evil.example": "93.184.216.34"}),
    )
    with pytest.raises(EgressError) as excinfo:
        policy("https://evil.example/x")
    assert "deny-listed" in str(excinfo.value)
    assert excinfo.value.host == "evil.example"


def test_allow_list_miss_blocked() -> None:
    policy = EgressPolicy(
        allowed_hosts=("api.example.com",),
        resolver=_resolver({"other.example": "93.184.216.34"}),
    )
    assert not policy.is_allowed("https://other.example/x")


def test_private_range_blocked_by_default() -> None:
    policy = EgressPolicy(resolver=_resolver({"internal": "10.0.0.5"}))
    with pytest.raises(EgressError):
        policy("http://internal/admin")


def test_loopback_and_metadata_blocked() -> None:
    policy = EgressPolicy(resolver=_resolver({"lb": "127.0.0.1", "meta": "169.254.169.254"}))
    with pytest.raises(EgressError):
        policy("http://lb/")
    with pytest.raises(EgressError):
        policy("http://meta/latest/meta-data/")


def test_allow_private_opt_in() -> None:
    policy = EgressPolicy(allow_private=True, resolver=_resolver({"internal": "10.0.0.5"}))
    policy("http://internal/ok")  # does not raise


def test_non_http_scheme_blocked() -> None:
    policy = EgressPolicy(resolver=_resolver({}))
    with pytest.raises(EgressError):
        policy("file:///etc/passwd")


def test_bad_denied_hosts_type_rejected() -> None:
    with pytest.raises(TypeError):
        EgressPolicy(denied_hosts="evil.example")  # type: ignore[arg-type]
