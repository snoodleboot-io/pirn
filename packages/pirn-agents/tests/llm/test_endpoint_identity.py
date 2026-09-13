"""Unit tests for :class:`pirn_agents.llm.endpoint_identity.EndpointIdentity` (PIR-840)."""

from __future__ import annotations

import unittest

from pirn_agents.llm.endpoint_identity import EndpointIdentity


class TestEndpointIdentityKeepsOnlyTheAllowlist(unittest.TestCase):
    def test_a_plain_url_is_reduced_to_scheme_host_port_and_path(self) -> None:
        # Arrange
        base_url = "HTTPS://Api.Example.COM:8443/v1/"

        # Act
        identity = EndpointIdentity.of(base_url)

        # Assert
        assert identity == {
            "scheme": "https",
            "host": "api.example.com",
            "port": 8443,
            "path": "/v1",
        }

    def test_an_absent_port_and_path_are_kept_as_absent(self) -> None:
        # Arrange / Act
        identity = EndpointIdentity.of("http://127.0.0.1")

        # Assert
        assert identity == {"scheme": "http", "host": "127.0.0.1", "port": None, "path": ""}

    def test_an_ipv6_host_is_named(self) -> None:
        # Arrange / Act
        identity = EndpointIdentity.of("http://[::1]:8000/v1")

        # Assert
        assert identity == {"scheme": "http", "host": "::1", "port": 8000, "path": "/v1"}

    def test_urls_carrying_more_than_the_allowlist_are_refused(self) -> None:
        refused = {
            "userinfo": "https://user:secret@api.example/v1",
            "username only": "https://token@api.example/v1",
            "query": "https://api.example/v1?api-version=2024-01-01",
            "empty query": "https://api.example/v1?",
            "credential query": "https://api.example/v1?X-Amz-Credential=AKIA",
            "fragment": "https://api.example/v1#section",
            "at sign in path": "https://api.example/v1/@me",
            "backslash": "https://api.example\\@evil.example/v1",
            "whitespace": "https://api.example/v1 ",
            "tab": "https://api.exa\tmple/v1",
            "non-ascii host": "https://bücher.example/v1",
            "non-http scheme": "ftp://api.example/v1",
            "no scheme": "api.example/v1",
            "no host": "https:///v1",
            "invalid port": "https://api.example:port/v1",
            "port out of range": "https://api.example:70000/v1",
            "empty": "",
        }
        for label, base_url in refused.items():
            with self.subTest(case=label):
                # Act / Assert
                assert EndpointIdentity.of(base_url) is None
