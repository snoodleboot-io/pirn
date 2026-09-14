"""``Router`` — shared interface for every routing knot.

The DIP seam behind the router family. A router inspects a request (a message,
task, score, or candidate set) and selects where it should go next — a branch, a
specialist, a tool, an escalation, or an ordered fallback chain. Across the
package this shape is implemented by ``specializations/routing/*``
(``IntentRouter``, ``CapabilityRouter``, ``CandidateRouter``,
``ConfidenceRouter``), plus ``OrchestratorRouter`` (multi-agent),
``CorrectiveRouter`` (RAG), ``EscalationRouter`` (human-in-the-loop), and
``ToolRouter`` (planning). Consolidating them onto one base lets callers depend
on the abstraction ``Router`` rather than each concrete, and gives every
concrete a single substitutable contract.

Following the house interface style (never :class:`typing.Protocol`), the base
is a :class:`~pirn.core.knot.Knot` whose :meth:`process` raises
:class:`NotImplementedError`; each concrete router overrides ``process`` with
its own keyword signature — exactly as it previously overrode ``Knot.process`` —
so the rebase changes no observable behavior.

Note:
    :class:`~pirn_agents.specializations.routing.model_cascade_router.ModelCascadeRouter`
    **is** a member of this family, as of PIR-718.

    It was previously excluded, and the exclusion was documented here as
    intentional. That reading was wrong: PIR-728, the story that wrote it, names
    the cascade router as one of the "9 routers, no ``Router`` base" and hands
    the shape question forward — "coordinate with WS7·S3/S6". The exclusion meant
    *not in that PR*, in a strictly behaviour-preserving story that could not
    afford to change a runtime surface. It was a deferral, not a decision, and
    PIR-718 discharges it.

    The port keeps the returned
    :class:`~pirn_agents.specializations.routing.cascade_outcome.CascadeOutcome`
    unchanged; only the constructor (now kwargs-only with ``_config``) and the
    entry point (``route`` → ``Knot.process``) moved.

References:
    - :class:`pirn.core.knot.Knot`
    - :class:`pirn.nodes.branch.branch.Branch`
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.err import Err
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.result import Result
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.branch.branch import Branch


class Router(Knot):
    """Abstract base for knots that route a request to a selected destination.

    Concrete routers subclass this and override :meth:`process` with their own
    keyword signature. The base itself is never placed in a graph directly; it
    exists so routers share one abstraction (DIP) and one substitutable contract
    (LSP): each ``process`` inspects a request and returns the chosen route,
    branch, or ordered candidate set.
    """

    # ``process`` below is declared in the gradual parameter form; see
    # ``Knot._dynamic_process_signature`` for why (PIR-833).
    _dynamic_process_signature: ClassVar[bool] = True

    async def process(self, *_args: Any, **_: Any) -> Any:
        """Select a destination for the given request.

        Concrete subclasses override this with their own keyword parameters and
        return type. The base raises to signal it is abstract.

        Raises:
            NotImplementedError: Always, on the base class.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement process()")

    @staticmethod
    def as_branch(
        *,
        route: Knot,
        branches: Mapping[str, Knot],
        _config: KnotConfig,
        tapestry: Any = None,
    ) -> Knot:
        """Select one of ``branches`` via a core ``Branch``, instead of a Python ``if route == ...``.

        Every branch's name-to-knot mapping is wired through a real
        :class:`~pirn.nodes.branch.branch.Branch` selecting on ``route``'s
        resolved value (which must already be one of ``branches``' keys —
        the same contract ``Branch`` itself enforces), so the selection is a
        graph decision the engine records (a lineage row naming the selected
        branch), not a decision hidden inside ``process()``'s Python control
        flow. Returns a single fused knot: whichever branch's arm resolved
        successfully.

        Laziness caveat (read before using this for an expensive arm):
        ``branches`` values are ordinary already-wired knots, wired as
        unconditional parents of the fused output. The engine still
        *schedules and runs every arm* — a non-selected arm's ``Result`` is
        simply dropped by :meth:`_pick_resolved`, but the arm knot itself is
        not prevented from executing, because it is not a *descendant* of
        its own ``BranchOutput`` the way ``branch.py``'s own docstring
        example wires downstream knots. This is safe for "route among a
        handful of already-known values" (the ``Mapping[str, Knot]`` shape
        this method takes matches, e.g., picking among fallback candidates);
        it is NOT a drop-in replacement for a pipeline whose Python ``if``
        exists specifically to avoid paying for an unselected arm's LLM
        call — that requires building the arm's own entry knot *from* its
        ``BranchOutput`` (a builder-callable API), a materially different,
        more invasive shape not implemented here (core gap noted in the ADR
        agents-speaks-core WS5a report).

        Args:
            route: Knot producing the route key — one of ``branches``' keys.
            branches: Non-empty mapping of route key to the (already wired)
                knot that produces that branch's result.
            _config: Config for the fused output knot. Internal helper nodes
                derive their ids from ``_config.id``.
            tapestry: Explicit tapestry to register with; ``None`` uses the
                ambient context-var tapestry (standard idiom).

        Returns:
            A single knot whose value is the selected branch's arm value.

        Raises:
            TypeError: If ``branches`` is empty.
        """
        if not branches:
            raise TypeError("Router.as_branch: branches must be non-empty")

        names = tuple(branches.keys())
        selector = Branch(
            input=route,
            selector=Router._identity,
            branches=names,
            _config=KnotConfig(id=f"{_config.id}:select"),
            tapestry=tapestry,
        )
        # Two parents per arm — its BranchOutput ("selected, or Skipped") and
        # its own value knot — rather than a per-arm gating Aggregator: a
        # gate combined under the DEFAULT error policy cannot tell "not
        # selected" (trigger Skipped) apart from "selected but the arm
        # itself failed" (trigger Ok, value Err) — both collapse to Skipped
        # (engine.py's `_decide`: `any_skipped or any_err -> Skipped`). Fusing
        # every (trigger, value) pair directly under RECEIVE_ERRORS lets
        # `_pick_resolved` tell them apart and keep the real failure message.
        parents: dict[str, Knot] = {}
        for name, arm in branches.items():
            parents[f"trigger__{name}"] = selector[name]
            parents[f"value__{name}"] = arm
        return Aggregator(
            combine=Router._pick_resolved,
            _config=KnotConfig(id=_config.id, error_policy=ErrorPolicy.RECEIVE_ERRORS),
            tapestry=tapestry,
            **parents,
        )

    @staticmethod
    def _identity(value: str) -> str:
        """Selector for :meth:`as_branch`: ``route``'s value already names the branch."""
        return value

    @staticmethod
    def _pick_resolved(**results: Result[Any]) -> Any:
        """Combine for :meth:`as_branch`'s fuse step: the one arm that was selected.

        Args:
            **results: ``trigger__<name>``/``value__<name>`` pairs, one pair
                per branch arm, each a raw ``Result`` (``RECEIVE_ERRORS``).

        Returns:
            The value of the selected arm (the one whose ``trigger`` is
            ``Ok`` — exactly one, since ``Branch`` selects exactly one arm).

        Raises:
            RuntimeError: If the selected arm's own value was ``Err`` or
                ``Skipped``, or if no arm was selected (an invariant
                violation — ``Branch`` always selects exactly one arm).
        """
        by_name: dict[str, dict[str, Result[Any]]] = {}
        for key, result in results.items():
            kind, _, name = key.partition("__")
            by_name.setdefault(name, {})[kind] = result

        for name, pair in by_name.items():
            if not isinstance(pair["trigger"], Ok):
                continue
            value = pair["value"]
            if isinstance(value, Ok):
                return value.value
            if isinstance(value, Err):
                raise RuntimeError(
                    f"Router.as_branch: selected arm {name!r} failed: "
                    f"{value.record.exc_type}: {value.record.message}"
                )
            raise RuntimeError(f"Router.as_branch: selected arm {name!r} was skipped")
        raise RuntimeError("Router.as_branch: no branch arm was selected")
