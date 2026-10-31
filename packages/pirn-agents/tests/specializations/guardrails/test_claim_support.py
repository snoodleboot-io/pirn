"""Tests for :class:`ClaimSupport`."""

from __future__ import annotations

import unittest

from pirn.core.payload import Payload

from pirn_agents.specializations.guardrails.claim_support import ClaimSupport
from pirn_agents.specializations.guardrails.claim_support_frame import ClaimSupportFrame


class TestClaimSupport(unittest.TestCase):
    def test_is_payload_with_frame_metadata(self) -> None:
        support = ClaimSupport("c", [{"fact": "c"}])
        assert isinstance(support, Payload)
        assert isinstance(support.metadata, ClaimSupportFrame)

    def test_supported_when_hits_present(self) -> None:
        support = ClaimSupport("c", [{"fact": "a"}, {"fact": "b"}])
        assert support.metadata.claim == "c"
        assert support.metadata.supported is True
        assert support.metadata.hit_count == 2

    def test_unsupported_when_no_hits(self) -> None:
        support = ClaimSupport("c", [])
        assert support.metadata.supported is False
        assert support.metadata.hit_count == 0
        assert support.data == ()

    def test_data_is_the_hits(self) -> None:
        assert ClaimSupport("c", [{"fact": "a"}]).data == ({"fact": "a"},)

    def test_audit_dict_has_both_halves_without_hit_contents(self) -> None:
        audit = ClaimSupport("c", [{"fact": "secret"}])._pirn_audit_dict()
        assert audit["claim"] == "c"
        assert audit["supported"] is True
        assert audit["hit_count"] == 1
        assert "secret" not in repr(audit)

    def test_equality_is_structural(self) -> None:
        assert ClaimSupport("c", [{"f": 1}]) == ClaimSupport("c", [{"f": 1}])
        assert ClaimSupport("c", [{"f": 1}]) != ClaimSupport("c", [])
