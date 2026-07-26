"""LSP contract tests for :class:`Router` and its concrete routers.

These pin the substitutability guarantees behind the router umbrella's DIP seam
(WS5 S7, PIR-728): the base is-a :class:`~pirn.core.knot.Knot` whose
:meth:`process` is abstract, every concrete router is-a ``Router`` (and
therefore a ``Knot``), and each concrete overrides ``process`` so it selects a
destination rather than raising the base ``NotImplementedError``.

:class:`~pirn_agents.specializations.routing.model_cascade_router.ModelCascadeRouter`
is intentionally excluded: it is a bare (non-``Knot``) class exposing a ``route``
coroutine rather than ``Knot.process``. The exclusion is pinned here so a future
rebase cannot quietly fold it into the family.

Per-concrete runtime round-trips live with each concrete's own suite (each
``process`` needs bespoke wiring); this module stays type/contract-focused.
"""

from __future__ import annotations

import unittest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.interfaces.router import Router
from pirn_agents.planning.tool_router import ToolRouter
from pirn_agents.specializations.human_in_the_loop.escalation_router import (
    EscalationRouter,
)
from pirn_agents.specializations.multi_agent.orchestrator_router import (
    OrchestratorRouter,
)
from pirn_agents.specializations.rag.corrective_router import CorrectiveRouter
from pirn_agents.specializations.routing.candidate_router import CandidateRouter
from pirn_agents.specializations.routing.capability_router import CapabilityRouter
from pirn_agents.specializations.routing.confidence_router import ConfidenceRouter
from pirn_agents.specializations.routing.intent_router import IntentRouter
from pirn_agents.specializations.routing.model_cascade_router import ModelCascadeRouter

CONCRETE_ROUTERS: tuple[type[Router], ...] = (
    IntentRouter,
    CapabilityRouter,
    CandidateRouter,
    ConfidenceRouter,
    OrchestratorRouter,
    CorrectiveRouter,
    EscalationRouter,
    ToolRouter,
)


def _bare(cls: type[Knot]) -> Knot:
    """Build a config-only knot instance, bypassing dependency wiring.

    ``process`` takes all of its inputs as explicit keyword arguments, so a bare
    instance is sufficient to exercise the abstract-base contract without a live
    graph.
    """
    with Tapestry():
        knot = cls.__new__(cls)
        object.__setattr__(knot, "_config", KnotConfig(id="x"))
    return knot


class TestBaseIsAbstractKnot(unittest.IsolatedAsyncioTestCase):
    def test_base_is_knot_subclass(self) -> None:
        # Arrange / Act / Assert
        assert issubclass(Router, Knot)

    async def test_base_process_raises_not_implemented_naming_class(self) -> None:
        # Arrange
        base = _bare(Router)
        # Act / Assert
        with self.assertRaisesRegex(NotImplementedError, "Router"):
            await base.process()


class TestConcreteSubstitutability(unittest.TestCase):
    def test_every_concrete_router_is_a_router(self) -> None:
        # Arrange / Act / Assert
        for cls in CONCRETE_ROUTERS:
            with self.subTest(router=cls.__name__):
                assert issubclass(cls, Router)
                assert issubclass(cls, Knot)

    def test_every_concrete_router_overrides_process(self) -> None:
        # Arrange / Act / Assert
        for cls in CONCRETE_ROUTERS:
            with self.subTest(router=cls.__name__):
                assert cls.process is not Router.process


class TestModelCascadeRouterExcluded(unittest.TestCase):
    def test_model_cascade_router_is_not_a_router(self) -> None:
        # Arrange / Act / Assert -- bare ``route`` class, not a family member.
        assert not issubclass(ModelCascadeRouter, Router)

    def test_model_cascade_router_is_not_a_knot(self) -> None:
        # Arrange / Act / Assert
        assert not issubclass(ModelCascadeRouter, Knot)


if __name__ == "__main__":
    unittest.main()
