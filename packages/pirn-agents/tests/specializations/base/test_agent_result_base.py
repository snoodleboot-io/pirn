"""LSP / substitutability contract tests for the ``AgentResult`` family (PIR-868).

PIR-868 rebases the eleven specialization ``*Result`` value objects from plain
frozen-dataclass ``AgentResult`` subclasses onto the ``Payload[Frame, Data]``
split established by ADR agents-speaks-core WS6b
(``AgentResponse = Payload[GenerationFrame, str]``,
``ConversationPayload = Payload[ConversationFrame, tuple[AgentMessage, ...]]``).
Each concrete is now :class:`~pirn_agents.specializations.base.agent_result.AgentResult`
parametrised with its own ``*Frame`` type and a data type — no longer a
dataclass at all; the base is a thin, non-abstract generic
:class:`~pirn.core.payload.Payload` subclass.

These tests pin the substitutability contract the rebase must preserve:

* the base is a non-dataclass ``Payload``/``PirnOpaqueValue`` subclass, and
* every concrete is a genuine ``AgentResult`` / ``Payload`` / ``PirnOpaqueValue``,
  overrides ``_pirn_audit_dict``, exposes its pre-ADR field names as read-only
  properties (hard-coded per class so the assertion cannot go vacuous), and
  compares equal to another instance built from the same field values.

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
import inspect

import pytest
from pirn.core.payload import Payload
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.specializations.base.agent_result import AgentResult

# (module_path, class_name, expected __init__ parameter order). The parameter
# tuple is a pinned literal -- NOT computed from the same runtime call the
# signature-order test asserts against, so the equality check is non-vacuous.
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

# A representative construction kwargs dict per result class, used by the
# equality and audit-dict tests below. Values are deliberately simple/opaque
# stand-ins, not exercised for domain meaning.
_SAMPLE_KWARGS: dict[str, dict[str, object]] = {
    "EvaluatorOptimizerResult": {
        "answer": "a",
        "score": 8.5,
        "accepted": True,
        "iterations": 2,
    },
    "LatsResult": {
        "best_trajectory": ("s1", "s2"),
        "best_value": 1.0,
        "nodes_expanded": 4,
        "budget_exhausted": False,
    },
    "SimulationResult": {
        "best_case": "g",
        "neutral_case": "n",
        "worst_case": "b",
    },
    "PromptChainResult": {
        "outputs": ("a", "b"),
        "final": "b",
    },
    "SelfAskResult": {
        "final_answer": "42",
        "subquestions": ("q1",),
        "subanswers": ("a1",),
    },
}

_RESULT_IDS = [name for _, name, _ in _RESULT_CLASSES]
_NON_RESULT_IDS = [name for _, name in _NON_RESULT_VALUE_OBJECTS]


def _load(module_path: str, class_name: str) -> type:
    """Import and return the class object at ``module_path.class_name``."""
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


# --- base identity -------------------------------------------------------


def test_agent_result_is_payload_and_opaque_value_and_not_a_dataclass() -> None:
    # Arrange / Act (identity is a static property of the base class).
    is_payload = issubclass(AgentResult, Payload)
    is_opaque = issubclass(AgentResult, PirnOpaqueValue)
    is_dataclass = dataclasses.is_dataclass(AgentResult)

    # Assert: the base carries both abstractions but declares no fields.
    assert is_payload is True
    assert is_opaque is True
    assert is_dataclass is False


def test_agent_result_requires_metadata_and_data_to_construct() -> None:
    # Arrange / Act / Assert: the base is a plain generic Payload -- it takes
    # no zero-arg construction, unlike the pre-ADR raising-hook base.
    with pytest.raises(TypeError):
        AgentResult()  # type: ignore[call-arg]


# --- concrete result LSP / field-preservation ----------------------------


@pytest.mark.parametrize(
    ("module_path", "class_name", "_expected"), _RESULT_CLASSES, ids=_RESULT_IDS
)
def test_result_is_agent_result_and_payload_and_opaque_value(
    module_path: str, class_name: str, _expected: tuple[str, ...]
) -> None:
    # Arrange.
    cls = _load(module_path, class_name)

    # Act / Assert: every concrete is substitutable for all three abstractions.
    assert issubclass(cls, AgentResult)
    assert issubclass(cls, Payload)
    assert issubclass(cls, PirnOpaqueValue)


@pytest.mark.parametrize(
    ("module_path", "class_name", "_expected"), _RESULT_CLASSES, ids=_RESULT_IDS
)
def test_result_is_not_a_dataclass(
    module_path: str, class_name: str, _expected: tuple[str, ...]
) -> None:
    # Arrange.
    cls = _load(module_path, class_name)

    # Act / Assert: concretes are plain Payload subclasses post-rebase, not
    # dataclasses -- matching AgentResponse/ConversationPayload (WS6b).
    assert dataclasses.is_dataclass(cls) is False


@pytest.mark.parametrize(
    ("module_path", "class_name", "_expected"), _RESULT_CLASSES, ids=_RESULT_IDS
)
def test_result_overrides_audit_dict(
    module_path: str, class_name: str, _expected: tuple[str, ...]
) -> None:
    # Arrange.
    cls = _load(module_path, class_name)

    # Act / Assert: each concrete supplies its own audit hook, not the
    # metadata-delegating one it inherits from Payload via AgentResult.
    assert cls._pirn_audit_dict is not Payload._pirn_audit_dict


@pytest.mark.parametrize(
    ("module_path", "class_name", "expected_params"), _RESULT_CLASSES, ids=_RESULT_IDS
)
def test_result_init_signature_preserves_pre_adr_field_order(
    module_path: str, class_name: str, expected_params: tuple[str, ...]
) -> None:
    # Arrange.
    cls = _load(module_path, class_name)

    # Act.
    actual_params = tuple(
        name for name in inspect.signature(cls.__init__).parameters if name != "self"
    )

    # Assert: the rebase introduces no parameter-order or naming drift, so
    # every existing keyword-argument call site keeps compiling.
    assert actual_params == expected_params


@pytest.mark.parametrize(
    ("module_path", "class_name", "expected_params"), _RESULT_CLASSES, ids=_RESULT_IDS
)
def test_result_exposes_every_field_as_a_read_only_property(
    module_path: str, class_name: str, expected_params: tuple[str, ...]
) -> None:
    # Arrange.
    cls = _load(module_path, class_name)

    # Act / Assert: every pre-ADR field name is a property with no setter.
    for name in expected_params:
        attr = inspect.getattr_static(cls, name)
        assert isinstance(attr, property), f"{class_name}.{name} is not a property"
        assert attr.fset is None, f"{class_name}.{name} must be read-only"


@pytest.mark.parametrize(
    ("class_name", "kwargs"), sorted(_SAMPLE_KWARGS.items()), ids=sorted(_SAMPLE_KWARGS)
)
def test_result_equality_by_value(class_name: str, kwargs: dict[str, object]) -> None:
    # Arrange.
    module_path = next(mp for mp, name, _ in _RESULT_CLASSES if name == class_name)
    cls = _load(module_path, class_name)

    # Act.
    a = cls(**kwargs)
    b = cls(**kwargs)

    # Assert: value equality is preserved despite dropping dataclass eq.
    assert a == b


@pytest.mark.parametrize(
    ("class_name", "kwargs"), sorted(_SAMPLE_KWARGS.items()), ids=sorted(_SAMPLE_KWARGS)
)
def test_result_properties_are_frozen(class_name: str, kwargs: dict[str, object]) -> None:
    # Arrange.
    module_path = next(mp for mp, name, _ in _RESULT_CLASSES if name == class_name)
    cls = _load(module_path, class_name)
    instance = cls(**kwargs)
    (first_field, _) = next(iter(kwargs.items()))

    # Act / Assert: no property has a setter, so assignment always raises.
    with pytest.raises(AttributeError):
        setattr(instance, first_field, "modified")


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
