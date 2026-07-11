"""Unit tests for :class:`pirn_agents.tool_permissions.ToolPermissions`."""

from __future__ import annotations

import unittest

from pirn_agents.tool_permissions import ToolPermissions


class TestToolPermissionsDefaults(unittest.TestCase):
    def test_default_is_unrestricted_and_inert(self) -> None:
        perms = ToolPermissions()
        assert perms.scope is None
        assert perms.mutating is False
        assert perms.approval_required is False
        assert perms.cost_hint is None
        assert perms.is_default is True

    def test_non_default_reports_not_default(self) -> None:
        assert ToolPermissions(scope="db:write").is_default is False
        assert ToolPermissions(mutating=True).is_default is False
        assert ToolPermissions(approval_required=True).is_default is False
        assert ToolPermissions(cost_hint=1.0).is_default is False


class TestToolPermissionsSchemaFragment(unittest.TestCase):
    def test_default_fragment_is_empty(self) -> None:
        assert ToolPermissions().as_schema_fragment() == {}

    def test_fragment_includes_only_non_default_fields(self) -> None:
        perms = ToolPermissions(scope="web:read", mutating=True, cost_hint=2.5)
        assert perms.as_schema_fragment() == {
            "scope": "web:read",
            "mutating": True,
            "cost_hint": 2.5,
        }

    def test_approval_flag_in_fragment(self) -> None:
        assert ToolPermissions(approval_required=True).as_schema_fragment() == {
            "approval_required": True
        }


class TestToolPermissionsValidation(unittest.TestCase):
    def test_scope_wrong_type_raises(self) -> None:
        with self.assertRaisesRegex(TypeError, "scope"):
            ToolPermissions(scope=123)  # type: ignore[arg-type]

    def test_mutating_wrong_type_raises(self) -> None:
        with self.assertRaisesRegex(TypeError, "mutating"):
            ToolPermissions(mutating="yes")  # type: ignore[arg-type]

    def test_cost_hint_wrong_type_raises(self) -> None:
        with self.assertRaisesRegex(TypeError, "cost_hint"):
            ToolPermissions(cost_hint="cheap")  # type: ignore[arg-type]

    def test_cost_hint_bool_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "cost_hint"):
            ToolPermissions(cost_hint=True)  # type: ignore[arg-type]

    def test_negative_cost_hint_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-negative"):
            ToolPermissions(cost_hint=-1.0)


class TestToolPermissionsAudit(unittest.TestCase):
    def test_audit_dict_round_trips_fields(self) -> None:
        perms = ToolPermissions(scope="s", mutating=True, approval_required=True, cost_hint=3.0)
        assert perms._pirn_audit_dict() == {
            "scope": "s",
            "mutating": True,
            "approval_required": True,
            "cost_hint": 3.0,
        }

    def test_frozen_is_hashable(self) -> None:
        assert ToolPermissions() == ToolPermissions()
        assert hash(ToolPermissions(scope="a")) == hash(ToolPermissions(scope="a"))


if __name__ == "__main__":
    unittest.main()
