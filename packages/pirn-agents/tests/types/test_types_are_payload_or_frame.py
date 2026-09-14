"""Ratchet: every class under ``pirn_agents.types`` is a ``Payload``, a frame, or allowlisted.

ADR agents-speaks-core WS6b: the vocabulary-drift review found agents had no
``Payload[Frame, Data]`` type at all — ``AgentResponse``/``AgentContext`` were
flat frozen dataclasses with no frame/metadata lineage descriptor and no
``derive()``. WS6b introduced ``AgentResponse = Payload[GenerationFrame, str]``
and ``ConversationPayload = Payload[ConversationFrame, tuple[AgentMessage,
...]]``. This test freezes the intent going forward: a class added under
``pirn_agents.types`` in the future is either

* a **Payload** — ``issubclass(cls, pirn.core.payload.Payload)`` — a typed
  ``(frame, data)`` pair that crosses a knot boundary, or
* a **frame** — a frozen :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`
  dataclass named ``*Frame`` that only ever appears as a Payload's
  ``metadata``, or
* explicitly **allowlisted** below, with a one-line reason, because it is a
  structural leaf embedded *inside* a Payload's data (a content block, a
  plain message record) rather than a knot-boundary value of its own.

Following the style of ``tests/specializations/base/test_no_engine_bypass.py``:
the allowlist is asserted by exact equality, so adding an unclassified class
fails (not in the list) and fixing/removing a class without updating the list
also fails (the list still names it).
"""

from __future__ import annotations

import ast
import importlib
import unittest
from pathlib import Path

from pirn.core.payload import Payload
from pirn.core.pirn_opaque_value import PirnOpaqueValue

_TYPES_ROOT = Path(__file__).resolve().parents[2] / "pirn_agents" / "types"

#: ``module::ClassName`` entries for classes that are neither a ``Payload``
#: nor a ``*Frame`` — each is a structural leaf carried *inside* a Payload's
#: data (a content block making up ``MessageContent``/``AgentMessage.blocks``,
#: or the plain ``AgentMessage`` record itself), not a knot-boundary value in
#: its own right. See the module docstring of each for its full rationale.
ALLOWLISTED_STRUCTURAL = frozenset(
    {
        # Content-block union: nested inside AgentMessage.blocks, never a
        # standalone knot output.
        "content.content_block::ContentBlock",
        "content.text_block::TextBlock",
        "content.image_block::ImageBlock",
        "content.audio_block::AudioBlock",
        "content.file_block::FileBlock",
        "content.tool_result_block::ToolResultBlock",
        "content.media_handle::MediaHandle",
        "content.message_content::MessageContent",
        # Plain message record: the element type of ConversationPayload's
        # `data` (tuple[AgentMessage, ...]) and AgentResponse's antecedent —
        # analogous to numpy.ndarray being SignalPayload's `data` type.
        "messaging.agent_message::AgentMessage",
        # Neutral string enum, not a value that flows through the graph on
        # its own.
        "messaging.finish_reason::FinishReason",
    }
)


def _iter_type_classes() -> list[tuple[str, type]]:
    """Import every module under ``pirn_agents.types`` and collect its classes.

    Returns:
        ``(module::ClassName, cls)`` pairs for every class defined
        (not merely imported) in a module under ``pirn_agents/types/``.
    """
    found: list[tuple[str, type]] = []
    for path in sorted(_TYPES_ROOT.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        relative = path.relative_to(_TYPES_ROOT).with_suffix("")
        dotted = ".".join(relative.parts)
        module = importlib.import_module(f"pirn_agents.types.{dotted}")
        tree = ast.parse(path.read_text())
        class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        for name in class_names:
            cls = getattr(module, name)
            found.append((f"{dotted}::{name}", cls))
    return found


class TestEveryTypeIsPayloadFrameOrAllowlisted(unittest.TestCase):
    def test_classification(self) -> None:
        unclassified: list[str] = []
        for qualname, cls in _iter_type_classes():
            is_payload = issubclass(cls, Payload)
            is_frame = (
                not is_payload
                and cls.__name__.endswith("Frame")
                and issubclass(cls, PirnOpaqueValue)
            )
            is_allowlisted = qualname in ALLOWLISTED_STRUCTURAL
            if not (is_payload or is_frame or is_allowlisted):
                unclassified.append(qualname)
        assert unclassified == [], (
            f"Unclassified pirn_agents.types class(es): {unclassified}. "
            "Make it a Payload subclass, a *Frame dataclass, or add it to "
            "ALLOWLISTED_STRUCTURAL with a documented reason."
        )

    def test_allowlist_entries_still_exist_and_are_not_payload_or_frame(self) -> None:
        """The other half of the ratchet: a fixed/removed entry must be deleted here too."""
        classes_by_qualname = dict(_iter_type_classes())
        for qualname in ALLOWLISTED_STRUCTURAL:
            assert qualname in classes_by_qualname, (
                f"{qualname} is allowlisted but no longer exists under pirn_agents.types; "
                "remove it from ALLOWLISTED_STRUCTURAL."
            )
            cls = classes_by_qualname[qualname]
            assert not issubclass(cls, Payload), (
                f"{qualname} is now a Payload subclass; remove it from ALLOWLISTED_STRUCTURAL."
            )
            assert not (cls.__name__.endswith("Frame") and issubclass(cls, PirnOpaqueValue)), (
                f"{qualname} is now a *Frame type; remove it from ALLOWLISTED_STRUCTURAL."
            )


# --- specializations/base *Result family (PIR-868) ------------------------
#
# PIR-868 rebased the eleven specialization ``*Result`` value objects
# (previously plain frozen-dataclass ``AgentResult`` subclasses) onto the same
# ``Payload[Frame, Data]`` split this module already ratchets for
# ``pirn_agents.types``. Those result/frame pairs live under
# ``specializations/<pattern>/``, not under ``pirn_agents/types/`` (they are
# specialization-pattern outcomes, not general messaging types), so they
# cannot be picked up by ``_iter_type_classes``'s directory walk -- this is an
# explicit, pinned module list rather than a second directory walk, since
# ``specializations/**`` also contains many Knot classes that are neither a
# Payload nor a *Frame and must not be swept into this ratchet.

# (dotted_module, ClassName) pairs for every AgentResult concrete and its Frame.
_RESULT_FAMILY_MODULES: list[tuple[str, str]] = [
    ("pirn_agents.specializations.base.agent_result", "AgentResult"),
    (
        "pirn_agents.specializations.evaluator_optimizer.evaluator_optimizer_frame",
        "EvaluatorOptimizerFrame",
    ),
    (
        "pirn_agents.specializations.evaluator_optimizer.evaluator_optimizer_result",
        "EvaluatorOptimizerResult",
    ),
    ("pirn_agents.specializations.lats.lats_frame", "LatsFrame"),
    ("pirn_agents.specializations.lats.lats_result", "LatsResult"),
    (
        "pirn_agents.specializations.multi_agent.orchestrator_workers_frame",
        "OrchestratorWorkersFrame",
    ),
    (
        "pirn_agents.specializations.multi_agent.orchestrator_workers_result",
        "OrchestratorWorkersResult",
    ),
    ("pirn_agents.specializations.multi_agent.worker_task_frame", "WorkerTaskFrame"),
    ("pirn_agents.specializations.multi_agent.worker_task_result", "WorkerTaskResult"),
    ("pirn_agents.specializations.plan_react.plan_react_frame", "PlanReActFrame"),
    ("pirn_agents.specializations.plan_react.plan_react_result", "PlanReActResult"),
    ("pirn_agents.specializations.prompt_chaining.prompt_chain_frame", "PromptChainFrame"),
    ("pirn_agents.specializations.prompt_chaining.prompt_chain_result", "PromptChainResult"),
    ("pirn_agents.specializations.reflection.simulation_frame", "SimulationFrame"),
    ("pirn_agents.specializations.reflection.simulation_result", "SimulationResult"),
    ("pirn_agents.specializations.reflexion.reflexion_frame", "ReflexionFrame"),
    ("pirn_agents.specializations.reflexion.reflexion_result", "ReflexionResult"),
    ("pirn_agents.specializations.rewoo.rewoo_frame", "ReWooFrame"),
    ("pirn_agents.specializations.rewoo.rewoo_result", "ReWooResult"),
    ("pirn_agents.specializations.routing.fallback_frame", "FallbackFrame"),
    ("pirn_agents.specializations.routing.fallback_result", "FallbackResult"),
    ("pirn_agents.specializations.self_ask.self_ask_frame", "SelfAskFrame"),
    ("pirn_agents.specializations.self_ask.self_ask_result", "SelfAskResult"),
]

_RESULT_FAMILY_IDS = [f"{mod}::{name}" for mod, name in _RESULT_FAMILY_MODULES]


class TestResultFamilyIsPayloadOrFrame(unittest.TestCase):
    """Extends this module's Payload-or-Frame ratchet to the AgentResult family."""

    def test_classification(self) -> None:
        for module_path, class_name in _RESULT_FAMILY_MODULES:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            is_payload = issubclass(cls, Payload)
            is_frame = (
                not is_payload
                and cls.__name__.endswith("Frame")
                and issubclass(cls, PirnOpaqueValue)
            )
            assert is_payload or is_frame, (
                f"{module_path}::{class_name} is neither a Payload subclass nor a "
                "*Frame PirnOpaqueValue dataclass."
            )
            if class_name == "AgentResult":
                # The thin generic base itself: a Payload, never a *Frame.
                assert is_payload
            elif class_name.endswith("Frame"):
                assert is_frame, f"{module_path}::{class_name} must be a *Frame, not a Payload."
            else:
                assert is_payload, f"{module_path}::{class_name} must be a Payload."
