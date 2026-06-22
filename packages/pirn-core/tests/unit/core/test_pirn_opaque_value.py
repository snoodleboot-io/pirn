from __future__ import annotations

import unittest

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pydantic import BaseModel


class _MyOpaque(PirnOpaqueValue):
    def __init__(self, name: str) -> None:
        self._name = name


class _CustomAudit(PirnOpaqueValue):
    def _pirn_audit_dict(self):
        return {"custom": "audit"}


class _Container(BaseModel):
    value: _MyOpaque

    model_config = {"arbitrary_types_allowed": True}


class TestPirnOpaqueValue(unittest.TestCase):
    def test_default_audit_dict_contains_type_name(self):
        obj = _MyOpaque("test")
        token = obj._pirn_audit_dict()
        self.assertIn("_MyOpaque", token)

    def test_default_audit_dict_contains_id(self):
        obj = _MyOpaque("test")
        token = obj._pirn_audit_dict()
        self.assertIn("@", token)

    def test_custom_audit_dict(self):
        obj = _CustomAudit()
        self.assertEqual(obj._pirn_audit_dict(), {"custom": "audit"})

    def test_pydantic_core_schema_validates_instance(self):
        obj = _MyOpaque("hello")
        container = _Container(value=obj)
        self.assertIs(container.value, obj)

    def test_pydantic_rejects_wrong_type(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            _Container(value="not an opaque")  # type: ignore[arg-type]

    def test_two_instances_have_different_tokens(self):
        a = _MyOpaque("a")
        b = _MyOpaque("b")
        self.assertNotEqual(a._pirn_audit_dict(), b._pirn_audit_dict())
