"""Unit tests for :class:`TypedMemoryValidator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory_management.typed_memory_validator import TypedMemoryValidator
from tests.memory_management.conftest import make_record


def _make_knot() -> TypedMemoryValidator:
    with Tapestry():
        return TypedMemoryValidator(record=make_record(id="r1"), _config=KnotConfig(id="tmv"))


class TestTypedMemoryValidator(unittest.IsolatedAsyncioTestCase):
    async def test_returns_valid_record_unchanged(self) -> None:
        knot = _make_knot()
        record = make_record(id="r1", kind="semantic")
        assert await knot.process(record=record) is record

    async def test_rejects_non_record(self) -> None:
        knot = _make_knot()
        with self.assertRaises(TypeError):
            await knot.process(record="bad")  # type: ignore[arg-type]

    async def test_accepts_kind_in_allowed_subset(self) -> None:
        knot = _make_knot()
        record = make_record(id="r1", kind="semantic")
        result = await knot.process(record=record, allowed_kinds=["semantic", "profile"])
        assert result is record

    async def test_rejects_kind_outside_allowed_subset(self) -> None:
        knot = _make_knot()
        record = make_record(id="r1", kind="episodic")
        with self.assertRaises(ValueError):
            await knot.process(record=record, allowed_kinds=["semantic"])

    async def test_rejects_bad_allowed_kind(self) -> None:
        knot = _make_knot()
        record = make_record(id="r1")
        with self.assertRaises(ValueError):
            await knot.process(record=record, allowed_kinds=["nope"])  # type: ignore[list-item]
