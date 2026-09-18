"""The framework's own root knots validate their inputs like any other knot.

``Reduce``, ``Gate``, ``Branch`` and ``BranchOutput`` each declare every input
on ``process()`` but used to wire themselves by hand through ``Knot._bootstrap``,
which builds no ``TypeAdapter``s at all -- so ``KnotConfig.validate_io`` was a
no-op for them and ``Reduce.process(of: list[Any])`` and
``Gate.process(check: bool | None)`` were never checked.  ``Aggregator`` and
``Parameter`` are genuine roots (dynamic parent names; a framework-managed
signature) and get validation of their own contract instead (PIR-873).
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.branch.branch import Branch
from pirn.nodes.check import Check
from pirn.nodes.gate.gate import Gate
from pirn.nodes.reduce_ import Reduce
from pirn.tapestry import Tapestry


class _Any(Knot):
    """A source whose declared output is ``Any``, so it can emit anything."""

    async def process(self, value: Any = None, **_: Any) -> Any:
        return value


class _Verdict(Check):
    """A check whose verdict is whatever it was configured with."""

    async def process(self, verdict: Any = True, **_: Any) -> bool:
        return verdict


class TestReduceValidatesItsInput(unittest.IsolatedAsyncioTestCase):
    async def test_a_non_list_input_is_an_error_not_a_crash_inside_combine(self) -> None:
        # Arrange: ``of`` is declared ``list[Any]``; the parent hands it a dict.
        with Tapestry():
            source = _Any(value={"a": 1}, _config=KnotConfig(id="src"))
            reduce = Reduce(of=source, combine=len, _config=KnotConfig(id="r"))

        # Act.
        result = await reduce({"of": {"a": 1}})

        # Assert: validated against the declared type, so it is an Err.
        self.assertIsInstance(result, Err)

    async def test_a_list_input_still_reduces(self) -> None:
        # Arrange.
        with Tapestry():
            source = _Any(value=[1, 2, 3], _config=KnotConfig(id="src2"))
            reduce = Reduce(of=source, combine=sum, _config=KnotConfig(id="r2"))

        # Act.
        result = await reduce({"of": [1, 2, 3]})

        # Assert.
        self.assertEqual(result, Ok(value=6))

    async def test_an_input_adapter_exists_for_every_declared_input(self) -> None:
        # Arrange / Act.
        with Tapestry():
            source = _Any(value=[1], _config=KnotConfig(id="src3"))
            reduce = Reduce(of=source, combine=sum, _config=KnotConfig(id="r3"))

        # Assert: nothing is silently unvalidated.
        self.assertEqual(set(reduce.input_names), {"of", "combine", "form", "initial"})


class TestGateValidatesItsCheck(unittest.IsolatedAsyncioTestCase):
    async def test_a_non_boolean_verdict_is_an_error(self) -> None:
        # Arrange: the check's resolved value is declared ``bool | None``.
        with Tapestry():
            source = _Any(value=1, _config=KnotConfig(id="gsrc"))
            check = _Verdict(verdict="yes-ish", _config=KnotConfig(id="gchk"))
            gate = Gate(input=source, check=check, _config=KnotConfig(id="g"))

        # Act.
        result = await gate({"input": 1, "check": "yes-ish"})

        # Assert.
        self.assertIsInstance(result, Err)

    async def test_a_boolean_verdict_opens_the_gate(self) -> None:
        # Arrange.
        with Tapestry():
            source = _Any(value=7, _config=KnotConfig(id="gsrc2"))
            check = _Verdict(verdict=True, _config=KnotConfig(id="gchk2"))
            gate = Gate(input=source, check=check, _config=KnotConfig(id="g2"))

        # Act.
        result = await gate({"input": 7, "check": True})

        # Assert.
        self.assertEqual(result, Ok(value=7))


class TestBranchValidatesItsInputs(unittest.IsolatedAsyncioTestCase):
    async def test_a_non_string_chosen_name_is_an_error_in_the_output(self) -> None:
        # Arrange: ``BranchOutput.process(chosen: str, ...)``.
        with Tapestry():
            source = _Any(value=1, _config=KnotConfig(id="bsrc"))
            branch = Branch(
                input=source,
                selector=lambda _v: "left",
                branches=("left", "right"),
                _config=KnotConfig(id="b"),
            )

        # Act: the branch handed its output a non-string selection.
        result = await branch["left"]({"chosen": 3, "passthrough": 1})

        # Assert.
        self.assertIsInstance(result, Err)

    async def test_the_branch_name_is_a_declared_input_not_hidden_state(self) -> None:
        # Arrange.
        with Tapestry():
            source = _Any(value=1, _config=KnotConfig(id="bsrc2"))
            branch = Branch(
                input=source,
                selector=lambda _v: "left",
                branches=("left", "right"),
                _config=KnotConfig(id="b2"),
            )

        # Assert: ``process()`` can be called standalone with plain values.
        self.assertEqual(
            await branch["left"].process(chosen="left", passthrough=42, branch_name="left"),
            42,
        )
        self.assertEqual(branch["left"].config_values["branch_name"], "left")


class TestAggregatorValidatesItsCombineContract(unittest.IsolatedAsyncioTestCase):
    def test_a_parent_combine_cannot_receive_is_refused_at_construction(self) -> None:
        # Arrange.
        def merge(left: int, right: int) -> int:
            return left + right

        # Act / Assert: a typo'd parent name used to fail only mid-run.
        with Tapestry():
            source = _Any(value=1, _config=KnotConfig(id="asrc"))
            with self.assertRaisesRegex(TypeError, "does not accept parent"):
                Aggregator(
                    combine=merge,
                    left=source,
                    rihgt=source,
                    _config=KnotConfig(id="agg"),
                )

    async def test_a_parent_value_is_validated_against_combines_hint(self) -> None:
        # Arrange.
        def merge(left: int, right: int) -> int:
            return left + right

        with Tapestry():
            source = _Any(value=1, _config=KnotConfig(id="asrc2"))
            agg = Aggregator(
                combine=merge, left=source, right=source, _config=KnotConfig(id="agg2")
            )

        # Act.
        result = await agg({"left": 1, "right": "not an int at all"})

        # Assert.
        self.assertIsInstance(result, Err)

    async def test_an_unannotated_combine_is_left_unvalidated(self) -> None:
        # Arrange: no declared contract, so nothing to check -- as for an
        # unannotated ``process()`` parameter.
        with Tapestry():
            source = _Any(value=1, _config=KnotConfig(id="asrc3"))
            agg = Aggregator(
                combine=lambda left, right: (left, right),
                left=source,
                right=source,
                _config=KnotConfig(id="agg3"),
            )

        # Act.
        result = await agg({"left": 1, "right": "anything"})

        # Assert.
        self.assertEqual(result, Ok(value=(1, "anything")))


class TestRootConfigIsChecked(unittest.TestCase):
    def test_an_aggregator_refuses_a_config_that_is_not_a_knot_config(self) -> None:
        with Tapestry():
            source = _Any(value=1, _config=KnotConfig(id="csrc"))
            with self.assertRaisesRegex(TypeError, "must be a KnotConfig instance"):
                Aggregator(
                    combine=lambda left: left,
                    left=source,
                    _config="not-a-config",  # pyright: ignore[reportArgumentType]  # the wrong type is the subject of the test
                )

    def test_a_parameter_refuses_a_config_that_is_not_a_knot_config(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(TypeError, "must be a KnotConfig instance"):
                Parameter("x", int, _config="not-a-config")  # pyright: ignore[reportArgumentType]  # the wrong type is the subject of the test

    def test_a_parameter_refuses_a_default_of_the_wrong_type(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(TypeError, "does not match the declared type"):
                Parameter("x", int, default="twelve", _config=KnotConfig(id="p"))

    def test_a_parameter_accepts_a_default_of_the_declared_type(self) -> None:
        with Tapestry():
            self.assertEqual(
                Parameter("x", int, default=12, _config=KnotConfig(id="p2")).default, 12
            )
