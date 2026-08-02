"""``AgentLoopPipeline`` — the seam for a specialization whose body is a loop.

A specialization pipeline is normally an :class:`AgentPipeline`: a
``SubTapestry`` whose ``process`` builds an inner graph and returns its sink.
Some pipelines instead *iterate* — refine-until-good, retry-until-success,
converse-until-done — and the core node for that is
:class:`~pirn.nodes.loop_sub_tapestry.LoopSubTapestry`.

Such a pipeline is genuinely **both** things, and this class says so once:

* a ``LoopSubTapestry``, which is its *execution shape*;
* an ``AgentPipeline``, which is its *family membership* — every ``SubTapestry``
  under ``specializations/`` belongs to the family, and
  ``tests/specializations/base/test_agent_pipeline_base.py`` enforces it.

MRO puts ``LoopSubTapestry`` first, so ``process`` resolves to the loop driver
and ``AgentPipeline`` contributes membership only. Subclasses inherit the
combination rather than re-deriving it.

Writing a loop pipeline
-----------------------

Implement ``step`` and ``fold``; the base owns the rest.

**``step`` and ``fold`` are synchronous.** A termination decision that is an
``await`` — "ask the LLM whether we are done" — therefore cannot be evaluated in
them. Express it as a **knot inside the iteration tapestry** and have ``fold``
read its output off the ``RunResult``. That is the sanctioned shape
(``docs/adr/WS7-engine-parity.md`` §7): the alternative, making ``step``/``fold``
async, keeps the terminating call outside the engine, which is the exact bypass
this programme exists to remove.

**A decision knot that must only run conditionally** needs a gate. Core
:class:`~pirn.nodes.gate.gate.Gate` passes a *single* parent through, so it
cannot by itself feed a knot that takes several inputs — join it with
:class:`~pirn_agents.specializations.base.gated_agent_response.GatedAgentResponse`
(or an equivalent join). When the gate is ``Skipped`` everything downstream is
skipped with it, so the conditional call is never paid for.

**A loop over work that can genuinely fail** — a flaky provider, a timeout, a
rate limit — should set ``_tolerate_iteration_failures = True``. ``fold`` then
receives the failed ``RunResult`` (``succeeded is False``, ``exceptions``
populated) and decides whether to retry or stop. Without it a single failed
iteration ends the whole loop.

Seed the initial state with a plain :class:`~pirn.core.parameter.Parameter`;
no bespoke ``Source`` is needed.

References:
    - :class:`pirn.nodes.loop_sub_tapestry.LoopSubTapestry`
    - :class:`pirn_agents.specializations.base.agent_pipeline.AgentPipeline`
"""

from __future__ import annotations

from typing import TypeVar

from pirn.nodes.loop_sub_tapestry import LoopSubTapestry

from pirn_agents.specializations.base.agent_pipeline import AgentPipeline

S = TypeVar("S")


class AgentLoopPipeline(LoopSubTapestry[S], AgentPipeline):
    """Abstract base for specialization pipelines whose body is an iterative loop.

    Concrete loops subclass this and implement ``step`` / ``fold``, exactly as
    for :class:`LoopSubTapestry`. The base adds nothing to the execution
    contract — it exists so the pipeline is a family member by construction, and
    so the constraints in the module docstring are stated in one place instead
    of being rediscovered per pipeline.
    """
