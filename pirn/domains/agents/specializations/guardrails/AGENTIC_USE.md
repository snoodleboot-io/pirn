`pirn.domains.agents.specializations.guardrails` provides input/output safety gates, hallucination detection, PII handling, and fact-checking knots — it does not contain LLM-based content moderation policies; those are user-supplied as prompts or external API calls.

---

## Mental model

Guardrails are gates: they let safe content pass and convert unsafe content to `Err` or `Skipped`. Wire them before the LLM call (input guardrails) and after (output guardrails). Every gate inherits from `Gate` — an `Err` result stops the knot chain; downstream knots are skipped.

The two-sided pattern — `InputGuardrailGate` before the LLM, `OutputGuardrailGate` after — is the standard safety sandwich.

---

## Source map

```
pirn/domains/agents/specializations/guardrails/
│
│  ── Input guardrails ──
├── input_guardrail_gate.py        InputGuardrailGate       — run input checks; Err if any check fails
├── input_message_scrubber.py      InputMessageScrubber     — normalize / sanitize input text before checks
├── pii_redactor_check.py          PiiRedactorCheck         — detect PII in input; Err or redact before forwarding
│
│  ── Output guardrails ──
├── output_guardrail_gate.py       OutputGuardrailGate      — run output checks; Err if any check fails
├── output_response_validator.py   OutputResponseValidator  — validate LLM output against schema or rules
├── pii_response_redactor.py       PiiResponseRedactor      — redact PII from LLM response before returning
│
│  ── Fact-checking ──
├── fact_claim_extractor.py        FactClaimExtractor       — extract verifiable claims from LLM output
├── fact_claim_verifier.py         FactClaimVerifier        — verify claims against a knowledge source
├── fact_check_gate.py             FactCheckGate            — Err if any claim fails verification
├── citation_grounder.py           CitationGrounder         — ground citations to source documents
│
│  ── Hallucination detection ──
└── hallucination_detector.py      HallucinationDetector    — score response for hallucination; Err if above threshold
```

---

## Canonical pattern

### Safety sandwich — input and output guardrails

```python
from pirn.domains.agents.specializations.guardrails.input_guardrail_gate import InputGuardrailGate
from pirn.domains.agents.specializations.guardrails.output_guardrail_gate import OutputGuardrailGate
from pirn import Tapestry, Parameter, KnotConfig, RunRequest

with Tapestry() as t:
    request   = Parameter("request", str)
    safe_in   = InputGuardrailGate(
        input=request,
        checks=[pii_check, prompt_injection_check],
        _config=KnotConfig(id="input-guard"),
    )
    response  = LlmCaller(prompt=safe_in, llm=my_llm, _config=KnotConfig(id="llm"))
    safe_out  = OutputGuardrailGate(
        output=response,
        checks=[pii_response_redactor, hallucination_detector],
        _config=KnotConfig(id="output-guard"),
    )
```

### Fact-check LLM output before returning

```python
from pirn.domains.agents.specializations.guardrails.fact_claim_extractor import FactClaimExtractor
from pirn.domains.agents.specializations.guardrails.fact_check_gate import FactCheckGate

with Tapestry() as t:
    response = LlmCaller(..., _config=KnotConfig(id="llm"))
    claims   = FactClaimExtractor(response=response, llm=my_llm,
                                   _config=KnotConfig(id="extract"))
    verified = FactCheckGate(claims=claims, knowledge_source=my_rag_store,
                              _config=KnotConfig(id="factcheck"))
```

---

## Anti-patterns

**Applying `HallucinationDetector` without a reference** — the detector needs a ground-truth document or retrieved context to compare against. Without a reference, it falls back to self-consistency scoring which is less reliable.

**Using `FactCheckGate` as a sole truth arbiter** — fact-checking via LLM has false positives. Use it to flag, not silently drop; configure `on_fail="err"` only for high-stakes pipelines.

---

## Constraints and gotchas

- **`InputGuardrailGate` and `OutputGuardrailGate` short-circuit on first failing check.** Checks run in order; the first `Err` stops evaluation. To collect all failures, use `OutputResponseValidator` with `collect_all=True`.
- **`PiiRedactorCheck(mode="err")` blocks the request entirely.** Use `mode="redact"` to strip PII and continue. Default is `"err"`.
- **`CitationGrounder` requires a retrieval store** to resolve citations to source text. It does not generate citations — it verifies and grounds ones already in the response.
- **All guardrail gates inherit from `Gate`** — `Err` is propagated to downstream knots as `Skipped` per the Gate contract.

---

## Quick reference

| Task | Knot |
|------|------|
| Block unsafe input | `InputGuardrailGate(checks=[...])` |
| Redact PII from input | `PiiRedactorCheck(mode="redact")` |
| Validate LLM output | `OutputGuardrailGate(checks=[...])` |
| Redact PII from output | `PiiResponseRedactor` |
| Detect hallucinations | `HallucinationDetector(reference=..., threshold=...)` |
| Fact-check claims | `FactClaimExtractor` → `FactCheckGate` |
| Ground citations | `CitationGrounder(response=..., store=...)` |

---

*See also: [specializations AGENTIC_USE.md](../AGENTIC_USE.md)*
