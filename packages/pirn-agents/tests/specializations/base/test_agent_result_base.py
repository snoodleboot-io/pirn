"""LSP / substitutability contract tests for the ``AgentResult`` family (PIR-702).

WS5/S5 re-parents the eleven specialization ``*Result`` value objects onto the
shared, non-dataclass base
:class:`~pirn_agents.specializations.base.agent_result.AgentResult` (itself a
plain :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue` subclass whose
:meth:`_pirn_audit_dict` raises). These tests pin the substitutability contract
that re-parent must preserve:

* the base is abstract (not a dataclass; its audit hook raises), and
* every concrete stays a frozen dataclass, is a genuine ``AgentResult`` /
  ``PirnOpaqueValue``, overrides ``_pirn_audit_dict``, and keeps its exact
  field order (hard-coded per class so the assertion cannot go vacuous).

The negative pins guard the seam from over-reach: sub-component frozen value
objects that are *not* top-level pattern results stay plain ``PirnOpaqueValue``
and must not be swept into the ``AgentResult`` family.

Concrete classes are resolved via :func:`importlib.import_module` inside the
test body so this module always COLLECTS cleanly even if a re-parent is still
in flight -- only the assertions turn red until it lands.
"""

from __future__ import annotations

import dataclasses
import importlib

import pytest
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.specializations.base.agent_result import AgentResult

# (module_path, class_name, expected_field_order). The field tuple is a pinned
# literal -- recorded from ``[f.name for f in dataclasses.fields(cls)]`` of the
# source dataclasses -- NOT computed from the same runtime call the field-order
# test asserts against, so the equality check is non-vacuous.
_RESULT_CLASSES: list[tuple[str, str, tuple[str, ...]]] = [
    (
        "pirn_agents.specializations.evaluator_optimizer.evaluator_optimizer_result",
        "EvaluatorOptimizerResult",
        ("answer", "score", "accepted", "iterations"),
    ),
    (
        "pirn_agents.specializations.lats.lats_result",
        "LatsResult",
        ("best_trajectory", "best_value", "nodes_expanded", "budget_exhausted"),
    ),
    (
        "pirn_agents.specializations.multi_agent.orchestrator_workers_result",
        "OrchestratorWorkersResult",
        ("results", "succeeded", "total"),
    ),
    (
        "pirn_agents.specializations.multi_agent.worker_task_result",
        "WorkerTaskResult",
        ("task", "result"),
    ),
    (
        "pirn_agents.specializations.plan_react.plan_react_result",
        "PlanReActResult",
        ("plan", "step_responses", "final"),
    ),
    (
        "pirn_agents.specializations.prompt_chaining.prompt_chain_result",
        "PromptChainResult",
        ("outputs", "final"),
    ),
    (
        "pirn_agents.specializations.reflection.simulation_result",
        "SimulationResult",
        ("best_case", "neutral_case", "worst_case"),
    ),
    (
        "pirn_agents.specializations.reflexion.reflexion_result",
        "ReflexionResult",
        ("answer", "succeeded", "iterations", "attempts"),
    ),
    (
        "pirn_agents.specializations.rewoo.rewoo_result",
        "ReWooResult",
        ("answer", "plan", "results"),
    ),
    (
        "pirn_agents.specializations.routing.fallback_result",
        "FallbackResult",
        ("succeeded", "chosen", "result", "attempted", "skipped"),
    ),
    (
        "pirn_agents.specializations.self_ask.self_ask_result",
        "SelfAskResult",
        ("final_answer", "subquestions", "subanswers"),
    ),
]

# Sub-component frozen value objects that must stay plain PirnOpaqueValue and
# must NOT be re-parented onto AgentResult (they are not top-level *Result
# pattern outcomes).
_NON_RESULT_VALUE_OBJECTS: list[tuple[str, str]] = [
    ("pirn_agents.specializations.evaluator_optimizer.judge_verdict", "JudgeVerdict"),
    ("pirn_agents.specializations.routing.route_candidate", "RouteCandidate"),
    ("pirn_agents.specializations.reflexion.reflexion_attempt", "ReflexionAttempt"),
]

_RESULT_IDS = [name for _, name, _ in _RESULT_CLASSES]
_NON_RESULT_IDS = [name for _, name in _NON_RESULT_VALUE_OBJECTS]


def _load(module_path: str, class_name: str) -> type:
    """Import and return the class object at ``module_path.class_name``."""
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


# --- base identity -------------------------------------------------------


def test_agent_result_is_opaque_value_subclass_and_not_a_dataclass() -> None:
    # Arrange / Act (identity is a static property of the base class).
    is_opaque = issubclass(AgentResult, PirnOpaqueValue)
    is_dataclass = dataclasses.is_dataclass(AgentResult)

    # Assert: the base carries the opaque contract but declares no fields.
    assert is_opaque is True
    assert is_dataclass is False


def test_agent_result_audit_dict_raises_not_implemented() -> None:
    # Arrange: the abstract base has no fields, so it constructs directly.
    result = AgentResult()

    # Act / Assert: the shared hook signals abstractness by name.
    with pytest.raises(NotImplementedError) as excinfo:
        result._pirn_audit_dict()

    assert "AgentResult must implement _pirn_audit_dict()" in str(excinfo.value)


# --- concrete result LSP / field-preservation ----------------------------


@pytest.mark.parametrize(
    ("module_path", "class_name", "_expected"), _RESULT_CLASSES, ids=_RESULT_IDS
)
def test_result_is_agent_result_and_opaque_value(
    module_path: str, class_name: str, _expected: tuple[str, ...]
) -> None:
    # Arrange.
    cls = _load(module_path, class_name)

    # Act / Assert: every concrete is substitutable for both abstractions.
    assert issubclass(cls, AgentResult)
    assert issubclass(cls, PirnOpaqueValue)


@pytest.mark.parametrize(
    ("module_path", "class_name", "_expected"), _RESULT_CLASSES, ids=_RESULT_IDS
)
def test_result_is_frozen_dataclass(
    module_path: str, class_name: str, _expected: tuple[str, ...]
) -> None:
    # Arrange.
    cls = _load(module_path, class_name)

    # Act / Assert: concretes remain frozen dataclasses despite the new base.
    assert dataclasses.is_dataclass(cls)
    assert cls.__dataclass_params__.frozen is True


@pytest.mark.parametrize(
    ("module_path", "class_name", "_expected"), _RESULT_CLASSES, ids=_RESULT_IDS
)
def test_result_overrides_audit_dict(
    module_path: str, class_name: str, _expected: tuple[str, ...]
) -> None:
    # Arrange.
    cls = _load(module_path, class_name)

    # Act / Assert: each concrete supplies its own audit hook, not the raising base.
    assert cls._pirn_audit_dict is not AgentResult._pirn_audit_dict


@pytest.mark.parametrize(
    ("module_path", "class_name", "expected_fields"), _RESULT_CLASSES, ids=_RESULT_IDS
)
def test_result_field_order_preserved(
    module_path: str, class_name: str, expected_fields: tuple[str, ...]
) -> None:
    # Arrange.
    cls = _load(module_path, class_name)

    # Act.
    actual_fields = tuple(f.name for f in dataclasses.fields(cls))

    # Assert: the re-parent introduces no field-order or default drift.
    assert actual_fields == expected_fields


# --- negative / scope pins -----------------------------------------------


@pytest.mark.parametrize(
    ("module_path", "class_name"), _NON_RESULT_VALUE_OBJECTS, ids=_NON_RESULT_IDS
)
def test_sub_component_value_objects_are_not_agent_results(
    module_path: str, class_name: str
) -> None:
    # Arrange.
    cls = _load(module_path, class_name)

    # Act / Assert: they stay plain opaque values, outside the AgentResult family.
    assert issubclass(cls, PirnOpaqueValue)
    assert not issubclass(cls, AgentResult)
