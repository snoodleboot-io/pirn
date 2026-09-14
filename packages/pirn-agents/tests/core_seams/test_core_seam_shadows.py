"""Ratchet: freeze the ``pirn_agents`` classes that shadow a WS0 core seam.

The "agents speaks core" ADR (2026-09-13) adds six seams to ``pirn-core`` in
WS0 so that agents can stop carrying parallel implementations of core verbs:
retry/timeout, nested-run depth and cycle guarding, declared input schemas,
admission-gate runtime feedback, the ``Check`` role, and an awaitable loop
step.  The classes below are the parallel implementations that exist today.
WS0 builds the seams; WS1-WS6 migrate each of these onto them, one PR at a
time, replacing every public name with a one-cycle deprecation shim that
subclasses the core seam class.

The allowlists are asserted by **exact equality**, deliberately:

* adding a new shadow fails, because the finding is not in the list;
* migrating one *without* updating the list also fails, because the list
  still names it.

The second half is what keeps the list from rotting into a lie.  When you
migrate a class, delete its line and watch this test go green.  A thin shim
that subclasses the core seam class (``class RetryPolicy(KnotRetryPolicy)``)
is not a shadow, so a migration that keeps the public name importable still
removes the entry.
"""

from __future__ import annotations

import ast
import unittest

from tests.core_seams.core_seam_shadow_inventory import CoreSeamShadowInventory

# --- known shadows, frozen (ADR agents-speaks-core, WS0) -------------------

# RetryPolicy and ToolTimeoutError deleted (PIR-872): KnotConfig.retry /
# KnotRetryPolicy.run and KnotConfig.timeout -> KnotTimeoutError.
RETRY_TIMEOUT: frozenset[str] = frozenset()

NESTING = frozenset(
    {
        "exceptions/agent_cycle_error.py::AgentCycleError",
        "exceptions/agent_depth_exceeded_error.py::AgentDepthExceededError",
        "exceptions/agent_recursion_error.py::AgentRecursionError",
    }
)

# AgentSchemaDeriver/ToolSchemaCompiler/ArgumentValidator all deleted (PIR-864).
INPUT_SCHEMA: frozenset[str] = frozenset()

# PIR-866 removed BackpressureSemaphore/Bulkhead as private-semaphore shadows:
# each became an AdmissionGate subclass, delegating every admission decision
# to a real LimitedAdmissionGate. PIR-864 then deleted BackpressureSemaphore,
# Bulkhead, ConcurrencyConfig, and BulkheadConfig outright, along with
# _FanoutRunner/AsyncFanoutEngine (WS1) and BatchScheduler (WS4b) -- every
# name this list ever named.
ADMISSION_FEEDBACK: frozenset[str] = frozenset()

CHECK_ROLE = frozenset(
    {
        "specializations/base/gated_agent_response.py::GatedAgentResponse",
    }
)

ASYNC_LOOP_STEP = frozenset(
    {
        "agent/parallel_tool_executor.py::ParallelToolExecutor",
    }
)


class TestCoreSeamShadowsAreFrozen(unittest.TestCase):
    """Freeze the shadow inventory.  Exact equality in both directions."""

    def setUp(self) -> None:
        self.found = CoreSeamShadowInventory.discover()

    def _assert_frozen(self, seam: str, expected: frozenset[str]) -> None:
        found = self.found[seam]
        assert found == expected, {
            "new shadows": sorted(found - expected),
            f"migrated — remove from {seam.upper()}": sorted(expected - found),
        }

    def test_the_walk_is_not_vacuous(self) -> None:
        """A guard that finds nothing passes for the wrong reason.

        Every seam inventory is empty now (PIR-872 migrated the last shadows),
        so the walk proves it ran by the classes it inspected, not by what it
        found; ``TestDetectorIsDiscriminating`` proves the detector still fires.
        """
        assert len(CoreSeamShadowInventory.top_level_classes()) >= 500

    def test_retry_and_timeout_shadows_are_frozen(self) -> None:
        self._assert_frozen("retry_timeout", RETRY_TIMEOUT)

    def test_nesting_guard_shadows_are_frozen(self) -> None:
        self._assert_frozen("nesting", NESTING)

    def test_input_schema_shadows_are_frozen(self) -> None:
        self._assert_frozen("input_schema", INPUT_SCHEMA)

    def test_admission_feedback_shadows_are_frozen(self) -> None:
        self._assert_frozen("admission_feedback", ADMISSION_FEEDBACK)

    def test_check_role_shadows_are_frozen(self) -> None:
        self._assert_frozen("check_role", CHECK_ROLE)

    def test_async_loop_step_shadows_are_frozen(self) -> None:
        self._assert_frozen("async_loop_step", ASYNC_LOOP_STEP)


class TestDetectorIsDiscriminating(unittest.TestCase):
    """The detector must fire on the shapes it names, and not on clean code."""

    @staticmethod
    def _class_of(source: str) -> ast.ClassDef:
        tree = ast.parse(source)
        return next(n for n in tree.body if isinstance(n, ast.ClassDef))

    def test_a_matching_name_with_no_core_base_is_a_shadow(self) -> None:
        node = self._class_of("class RetryPolicy(PirnOpaqueValue):\n    pass\n")
        assert CoreSeamShadowInventory.is_shadow(node, "retry_timeout")

    def test_a_shim_over_the_core_seam_class_is_not_a_shadow(self) -> None:
        node = self._class_of("class RetryPolicy(KnotRetryPolicy):\n    pass\n")
        assert not CoreSeamShadowInventory.is_shadow(node, "retry_timeout")

    def test_a_dotted_core_base_is_recognised(self) -> None:
        node = self._class_of("class AgentCycleError(exceptions.NestedRunCycleError):\n    pass\n")
        assert not CoreSeamShadowInventory.is_shadow(node, "nesting")

    def test_a_generic_core_base_is_recognised(self) -> None:
        node = self._class_of("class ParallelToolExecutor(LoopSubTapestry[int]):\n    pass\n")
        assert not CoreSeamShadowInventory.is_shadow(node, "async_loop_step")

    def test_an_unrelated_name_is_not_a_shadow(self) -> None:
        node = self._class_of("class ToolCall:\n    pass\n")
        assert not any(
            CoreSeamShadowInventory.is_shadow(node, seam) for seam in CoreSeamShadowInventory.SEAMS
        )

    def test_a_shadow_matches_exactly_one_seam(self) -> None:
        node = self._class_of("class GatedAgentResponse(Knot):\n    pass\n")
        seams = [
            s for s in CoreSeamShadowInventory.SEAMS if CoreSeamShadowInventory.is_shadow(node, s)
        ]
        assert seams == ["check_role"]
