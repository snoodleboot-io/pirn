"""Tests for :class:`ClaimSupportFrame`."""

from __future__ import annotations

import unittest

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.specializations.guardrails.claim_support_frame import ClaimSupportFrame


class TestClaimSupportFrame(unittest.TestCase):
    def test_is_opaque_value(self) -> None:
        assert isinstance(ClaimSupportFrame("c", True, 1), PirnOpaqueValue)

    def test_audit_dict_carries_every_field(self) -> None:
        frame = ClaimSupportFrame("water is wet", True, 2)
        assert frame._pirn_audit_dict() == {
            "claim": "water is wet",
            "supported": True,
            "hit_count": 2,
        }

    def test_equality_is_structural(self) -> None:
        assert ClaimSupportFrame("c", False, 0) == ClaimSupportFrame("c", False, 0)
        assert ClaimSupportFrame("c", False, 0) != ClaimSupportFrame("c", True, 1)
