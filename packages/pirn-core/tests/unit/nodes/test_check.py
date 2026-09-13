"""Unit tests for ``Check`` (ADR agents-speaks-core, WS0)."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.optional import Optional
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.skipped import Skipped
from pirn.nodes.check import Check
from pirn.tapestry import Tapestry


class _Positive(Check):
    async def process(self, value: int, **_: Any) -> bool:
        return value > 0


class _Both(Check):
    """Reads two parents: the role is not limited to one input."""

    async def process(self, left: int, right: int, **_: Any) -> bool:
        return left == right


class _Leaky(Check):
    async def process(self, value: int, **_: Any) -> Any:
        return value  # truthy, but not a verdict


class _Raises(Check):
    async def process(self, value: int, **_: Any) -> bool:
        raise ValueError("cannot decide")


def _upstream(value: int = 1, knot_id: str = "up") -> Parameter:
    return Parameter(knot_id, int, default=value, _config=KnotConfig(id=knot_id))


class TestCheckContract(unittest.IsolatedAsyncioTestCase):
    async def test_base_process_must_be_implemented(self) -> None:
        check = Check(_config=KnotConfig(id="c"))
        with self.assertRaisesRegex(NotImplementedError, "process"):
            await check.process()

    async def test_a_true_verdict_is_ok_true(self) -> None:
        check = _Positive(value=_upstream(), _config=KnotConfig(id="c"))
        self.assertEqual(await check({"value": 3}), Ok(value=True))

    async def test_a_false_verdict_is_ok_false(self) -> None:
        check = _Positive(value=_upstream(), _config=KnotConfig(id="c"))
        self.assertEqual(await check({"value": -3}), Ok(value=False))

    async def test_a_non_bool_verdict_is_an_err(self) -> None:
        check = _Leaky(value=_upstream(), _config=KnotConfig(id="c"))
        result = await check({"value": 3})
        self.assertIsInstance(result, Err)
        assert isinstance(result, Err)
        self.assertEqual(result.record.exc_type, "TypeError")
        self.assertIn("must return a bool", result.record.message)

    async def test_the_bool_contract_holds_without_validate_io(self) -> None:
        check = _Leaky(value=_upstream(), _config=KnotConfig(id="c", validate_io=False))
        self.assertIsInstance(await check({"value": 3}), Err)

    async def test_a_raising_check_is_an_err(self) -> None:
        check = _Raises(value=_upstream(), _config=KnotConfig(id="c"))
        result = await check({"value": 3})
        assert isinstance(result, Err)
        self.assertEqual(result.record.exc_type, "ValueError")

    async def test_a_check_may_read_several_parents(self) -> None:
        with Tapestry() as t:
            _Both(
                left=_upstream(2, "l"),
                right=_upstream(2, "r"),
                _config=KnotConfig(id="same"),
            )
        result = await t.run(RunRequest())
        self.assertIs(result.outputs["same"], True)

    async def test_an_optional_check_still_answers_a_bool_or_skips(self) -> None:
        with Tapestry() as t:
            Optional(_Raises, value=_upstream(), _config=KnotConfig(id="opt"))
        result = await t.run(RunRequest())
        self.assertIsInstance(result.outputs["opt"], Skipped)
