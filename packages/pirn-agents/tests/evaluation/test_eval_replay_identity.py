"""A recorded eval replays only for the same code, not just the same names (PIR-872).

The target and metrics are identified by their code (``CallableIdentity``), so an
edited body under an unchanged ``module.qualname`` refuses to replay, an unchanged
function replays even as a fresh function object, and a ``functools.partial``
with different bound arguments refuses.
"""

from __future__ import annotations

import functools
import unittest
from collections.abc import Callable, Mapping
from typing import Any

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.recording.replay_mismatch_error import ReplayMismatchError
from pirn.recording.replay_session import ReplaySession

from pirn_agents.evaluation.callable_identity import CallableIdentity
from pirn_agents.evaluation.eval_dataset import EvalDataset
from pirn_agents.evaluation.eval_item import EvalItem
from pirn_agents.evaluation.eval_report import EvalReport
from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.run_eval import RunEval


class _Sources:
    """Build functions from source text under one fixed module and qualname."""

    target_v1: str = (
        "async def target(item_input):\n"
        "    calls.append(item_input['q'])\n"
        "    return {'answer': item_input['q']}\n"
    )
    target_v2: str = (
        "async def target(item_input):\n"
        "    calls.append(item_input['q'])\n"
        "    return {'answer': str(item_input['q']).upper()}\n"
    )

    @staticmethod
    def build(source: str, name: str, **scope: Any) -> Callable[..., Any]:
        namespace: dict[str, Any] = dict(scope)
        exec(source, namespace)
        function = namespace[name]
        function.__module__ = "tests.evaluation.eval_subject_fixture"
        function.__qualname__ = name
        return function


class _Scale:
    @staticmethod
    def metric(item: EvalItem, output: Mapping[str, Any], *, factor: float) -> MetricResult:
        return MetricResult(name="scaled", score=factor * len(str(output["answer"])))

    @staticmethod
    def length(item: EvalItem, output: Mapping[str, Any]) -> MetricResult:
        return MetricResult(name="length", score=float(len(str(output["answer"]))))


def _dataset() -> EvalDataset:
    return EvalDataset(
        items=(
            EvalItem(item_id="a", input={"q": "paris"}),
            EvalItem(item_id="b", input={"q": "tokyo"}),
        )
    )


class TestReplayIdentityFollowsTheCode(unittest.IsolatedAsyncioTestCase):
    async def _record(
        self, target: Any, metrics: Mapping[str, Any]
    ) -> tuple[InMemoryHistory, InMemoryDataStore, EvalReport]:
        history = InMemoryHistory()
        store = InMemoryDataStore()
        report = await RunEval.run(
            dataset=_dataset(),
            target=target,
            metrics=metrics,
            history=history,
            data_store=store,
            run_id="recorded",
        )
        return history, store, report

    async def _replay(
        self, history: InMemoryHistory, store: InMemoryDataStore, target: Any, metrics: Any
    ) -> EvalReport:
        session = await ReplaySession.from_history(history=history, run_id="recorded")
        return await RunEval.run(
            dataset=_dataset(),
            target=target,
            metrics=metrics,
            history=history,
            data_store=store,
            replay=session,
        )

    async def test_an_edited_body_under_the_same_name_is_refused(self) -> None:
        # Arrange
        calls: list[str] = []
        recorded_target = _Sources.build(_Sources.target_v1, "target", calls=calls)
        edited_target = _Sources.build(_Sources.target_v2, "target", calls=calls)
        assert CallableIdentity._name(recorded_target) == CallableIdentity._name(edited_target)
        history, store, _ = await self._record(recorded_target, {"length": _Scale.length})

        # Act / Assert
        with self.assertRaises(ReplayMismatchError):
            await self._replay(history, store, edited_target, {"length": _Scale.length})
        assert calls == ["paris", "tokyo"]

    async def test_an_unchanged_function_replays_even_as_a_new_object(self) -> None:
        calls: list[str] = []
        recorded_target = _Sources.build(_Sources.target_v1, "target", calls=calls)
        history, store, recorded = await self._record(recorded_target, {"length": _Scale.length})
        rebuilt_calls: list[str] = []
        rebuilt_target = _Sources.build(_Sources.target_v1, "target", calls=rebuilt_calls)
        assert rebuilt_target is not recorded_target

        replayed = await self._replay(history, store, rebuilt_target, {"length": _Scale.length})

        assert rebuilt_calls == []
        assert replayed.to_json() == recorded.to_json()

    async def test_a_partial_with_different_bound_arguments_is_refused(self) -> None:
        calls: list[str] = []
        target = _Sources.build(_Sources.target_v1, "target", calls=calls)
        history, store, _ = await self._record(
            target, {"scaled": functools.partial(_Scale.metric, factor=1.0)}
        )

        with self.assertRaises(ReplayMismatchError):
            await self._replay(
                history, store, target, {"scaled": functools.partial(_Scale.metric, factor=2.0)}
            )

    async def test_a_partial_with_the_same_bound_arguments_replays(self) -> None:
        calls: list[str] = []
        target = _Sources.build(_Sources.target_v1, "target", calls=calls)
        history, store, recorded = await self._record(
            target, {"scaled": functools.partial(_Scale.metric, factor=1.0)}
        )

        replayed = await self._replay(
            history, store, target, {"scaled": functools.partial(_Scale.metric, factor=1.0)}
        )

        assert calls == ["paris", "tokyo"]
        assert replayed.to_json() == recorded.to_json()


class _Adder:
    def __init__(self, offset: int) -> None:
        self.offset = offset

    def add(self, value: int) -> int:
        return value + self.offset

    def __call__(self, value: int) -> int:
        return value + self.offset


class TestCallableIdentity(unittest.TestCase):
    def test_a_lambda_edit_changes_the_identity(self) -> None:
        first = _Sources.build("f = lambda x: x + 1\n", "f")
        second = _Sources.build("f = lambda x: x + 2\n", "f")
        assert CallableIdentity.of(first) != CallableIdentity.of(second)

    def test_a_nested_function_edit_changes_the_identity(self) -> None:
        source = "def outer():\n    def inner():\n        return {value}\n    return inner()\n"
        first = _Sources.build(source.format(value=1), "outer")
        second = _Sources.build(source.format(value=2), "outer")
        assert CallableIdentity.of(first) != CallableIdentity.of(second)

    def test_closure_values_are_part_of_the_identity(self) -> None:
        source = "def make(n):\n    def use(x):\n        return x + n\n    return use\n"
        make = _Sources.build(source, "make")
        assert CallableIdentity.of(make(1)) != CallableIdentity.of(make(2))
        assert CallableIdentity.of(make(1)) == CallableIdentity.of(make(1))

    def test_defaults_are_part_of_the_identity(self) -> None:
        first = _Sources.build("def f(x, k=1):\n    return x\n", "f")
        second = _Sources.build("def f(x, k=2):\n    return x\n", "f")
        assert CallableIdentity.of(first) != CallableIdentity.of(second)

    def test_a_bound_method_names_its_code(self) -> None:
        identity = CallableIdentity.of(_Adder(1).add)
        assert "method" in identity
        assert "code" in identity["method"]

    def test_a_callable_object_is_identified_by_its_call_code(self) -> None:
        identity = CallableIdentity.of(_Adder(1))
        assert "code" in identity["call"]

    def test_a_c_builtin_falls_back_to_its_name(self) -> None:
        assert CallableIdentity.of(len) == {"name": "builtins.len"}

    def test_a_self_referencing_closure_terminates(self) -> None:
        source = (
            "def make():\n"
            "    def again(n):\n"
            "        return again(n - 1) if n else 0\n"
            "    return again\n"
        )
        again = _Sources.build(source, "make")()
        assert CallableIdentity.of(again) == CallableIdentity.of(again)


if __name__ == "__main__":
    unittest.main()
