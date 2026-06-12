`pirn.domains.agents.specializations.multi_agent` provides patterns for coordinating multiple agents — it does not spawn processes or manage agent lifecycles; agents are knots that call an LLM, and coordination is wiring.

---

## Mental model

Multi-agent patterns are composed from two primitives: **fan-out** (send one problem to N specialists in parallel) and **aggregation** (combine N results into one). The patterns here wire those primitives into higher-level coordination strategies: orchestrator-worker delegation, parallel specialist panels, consensus voting, and structured debate.

Every agent in a multi-agent tapestry is a `LlmCaller`-backed knot. The coordinator role is itself an LLM call that decides routing or synthesis.

---

## Source map

```
pirn/domains/agents/specializations/multi_agent/
├── orchestrator_agent.py           OrchestratorAgent           — LLM decides which specialist to delegate to
├── orchestrator_router.py          OrchestratorRouter          — route result of orchestrator decision to knot
├── parallel_specialist_fan_out.py  ParallelSpecialistFanOut    — send same input to N specialist agents in parallel
├── specialist_fan_out_collector.py SpecialistFanOutCollector   — collect N parallel outputs into a list
├── consensus_aggregator.py         ConsensusAggregator         — combine N answers; pick by majority vote or synthesis
├── consensus_majority_vote_picker.py ConsensusMajorityVotePicker — vote on which answer is most common
├── consensus_synthesis_caller.py   ConsensusSynthesisCaller    — call LLM to synthesize N divergent answers
├── debate_framework.py             DebateFramework             — structured debate: propose → challenge → defend → judge
├── debate_judge.py                 DebateJudge                 — LLM judge picks winner after debate rounds
└── round_robin_review.py           RoundRobinReview            — pass output through N agents in sequence for review
```

---

## Canonical pattern

### Parallel specialists with consensus

```python
from pirn.domains.agents.specializations.multi_agent.parallel_specialist_fan_out import ParallelSpecialistFanOut
from pirn.domains.agents.specializations.multi_agent.consensus_aggregator import ConsensusAggregator
from pirn import Tapestry, Parameter, KnotConfig, RunRequest

with Tapestry() as t:
    question  = Parameter("question", str)
    responses = ParallelSpecialistFanOut(
        input=question,
        agents=[legal_agent, finance_agent, risk_agent],
        _config=KnotConfig(id="fan-out"),
    )
    answer    = ConsensusAggregator(
        responses=responses,
        llm=synthesis_llm,
        strategy="synthesis",   # or "majority_vote"
        _config=KnotConfig(id="consensus"),
    )
```

### Orchestrator-worker delegation

```python
from pirn.domains.agents.specializations.multi_agent.orchestrator_agent import OrchestratorAgent

with Tapestry() as t:
    request = Parameter("request", str)
    result  = OrchestratorAgent(
        request=request,
        workers={"code": code_agent, "research": research_agent, "sql": sql_agent},
        llm=orchestrator_llm,
        _config=KnotConfig(id="orchestrator"),
    )
```

---

## Anti-patterns

**Using `DebateFramework` for simple factual questions** — debate is expensive (multiple LLM rounds per agent). Use it only for genuinely contested decisions or adversarial verification tasks.

**Unbounded `ParallelSpecialistFanOut` with many agents** — each agent is an LLM call. Set a budget on `max_agents` or use `OrchestratorAgent` to route to a single specialist instead of broadcasting.

---

## Constraints and gotchas

- **`OrchestratorAgent` makes an LLM call to decide routing** — this adds latency and one extra token budget. For deterministic routing, use `IntentRouter` from `pirn.domains.agents.specializations.routing` instead.
- **`DebateFramework` requires at least 2 agents and a `DebateJudge`.** Each debate round adds `N_agents × rounds` LLM calls.
- **`ConsensusAggregator(strategy="majority_vote")` requires outputs that are comparable strings or enums.** For free-text answers, use `strategy="synthesis"` to call the LLM to reconcile.

---

## Quick reference

| Pattern | Entry point |
|---------|------------|
| Route to one specialist | `OrchestratorAgent(workers={...}, llm=...)` |
| Parallel specialists → consensus | `ParallelSpecialistFanOut` + `ConsensusAggregator` |
| Sequential review chain | `RoundRobinReview(agents=[...])` |
| Adversarial debate | `DebateFramework(agents=[...], judge=DebateJudge(...))` |
| Majority vote | `ConsensusMajorityVotePicker(responses=...)` |

---

*See also: [specializations AGENTIC_USE.md](../AGENTIC_USE.md)*
