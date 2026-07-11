`pirn_agents.specializations.structured_output` provides pipelines that extract typed, schema-validated data from LLM responses — it does not define the output schema; pass a Pydantic model class, JSON schema dict, YAML template, or enum class as the target type.

---

## Mental model

LLMs produce text. Structured output pipelines parse that text into a typed Python value, retrying with corrective prompts if parsing fails. Each pipeline variant targets a different output format: JSON object, YAML, typed enum, or an arbitrary Pydantic model. All pipelines end with a validated Python value or raise `Err` after exhausting retries.

The retry mechanism is the key feature: on `ValidationError` or parse failure, the pipeline re-prompts the LLM with the error message, giving it a chance to correct its output.

---

## Source map

```
pirn_agents/specializations/structured_output/
│
│  ── Pipeline knots ──
├── json_extractor_pipeline.py       JsonExtractorPipeline       — extract a dict conforming to a JSON schema
├── yaml_extractor_pipeline.py       YamlExtractorPipeline       — extract a dict from YAML-formatted LLM output
├── enum_classifier_pipeline.py      EnumClassifierPipeline      — classify input as one member of an enum
├── pydantic_validator_pipeline.py   PydanticValidatorPipeline   — extract + validate against a Pydantic model
│
│  ── Shared helpers ──
├── retry_on_parse_failure.py        RetryOnParseFailure         — wrap any extractor; retry N times with error feedback
├── format_coercer.py                FormatCoercer               — coerce LLM output to target format before parsing
├── schema_enforcer.py               SchemaEnforcer              — validate parsed dict against a JSON schema
│
│  ── Native single-pass (F20) ──
├── structured_decoder.py            StructuredDecoder / structured_decode — unified, capability-gated entry point
├── native_schema_mapper.py          NativeSchemaMapper          — S1: schema → native response_format request
├── forced_tool_choice_extractor.py  ForcedToolChoiceExtractor   — S2: force one synthetic extraction tool
├── constrained_decoding_mapper.py   ConstrainedDecodingMapper   — S3: schema → grammar/regex decode options
├── structured_output_capability.py  StructuredOutputCapability  — provider capability flags value object
├── structured_output_provider.py    StructuredOutputProvider    — provider protocol the native paths use
│
│  ── Internal attempt knots ──
├── _json_extractor_attempt.py       (internal — single JSON parse attempt)
├── _yaml_extractor_attempt.py       (internal — single YAML parse attempt)
├── _enum_classifier_attempt.py      (internal — single enum classification attempt)
└── _llm_call_knot.py                (internal — LLM call shared by all pipelines)
```

---

## Canonical pattern

### Extract a Pydantic model

```python
from pirn_agents.specializations.structured_output.pydantic_validator_pipeline import PydanticValidatorPipeline
from pydantic import BaseModel
from pirn import Tapestry, Parameter, KnotConfig, RunRequest

class Invoice(BaseModel):
    vendor: str
    amount: float
    currency: str
    date: str

with Tapestry() as t:
    text    = Parameter("text", str)
    invoice = PydanticValidatorPipeline(
        text=text,
        model=Invoice,
        llm=my_llm,
        max_retries=3,
        _config=KnotConfig(id="extract"),
    )
```

### Enum classification

```python
from enum import Enum
from pirn_agents.specializations.structured_output.enum_classifier_pipeline import EnumClassifierPipeline

class Sentiment(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL  = "neutral"

with Tapestry() as t:
    text      = Parameter("text", str)
    sentiment = EnumClassifierPipeline(
        text=text, target_enum=Sentiment, llm=my_llm, _config=KnotConfig(id="classify")
    )
```

### JSON extraction with schema

```python
from pirn_agents.specializations.structured_output.json_extractor_pipeline import JsonExtractorPipeline

schema = {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer"}}}

with Tapestry() as t:
    text   = Parameter("text", str)
    person = JsonExtractorPipeline(text=text, schema=schema, llm=my_llm,
                                    _config=KnotConfig(id="extract"))
```

---

## Native single-pass decoding (F20)

Beyond the retry pipelines above, `structured_decode` / `StructuredDecoder` add a
**unified, capability-gated** entry point that guarantees valid output in one
pass where the provider supports it, and otherwise falls back to the same
extract-validate-retry pipelines. Every route returns the *same* validated
Pydantic instance.

**Selection order** (each step is used only if the provider advertises it via
`structured_output_capability()`, else the next is tried; if none apply — or a
native attempt yields invalid output — it falls back to the retry pipeline):

1. **Native schema** (S1) — maps the target schema to the provider's native
   `response_format`/schema request (`NativeSchemaMapper`).
2. **Forced tool-choice** (S2) — forces a single synthetic extraction tool and
   validates its decoded arguments (`ForcedToolChoiceExtractor`, via F1's
   `ToolCallCodec`).
3. **Constrained decoding** (S3) — passes a generated grammar/regex constraint
   through a local engine's decode options (`ConstrainedDecodingMapper`;
   optional grammar compilation needs `pip install "pirn-agents[grammar]"`).
4. **Fallback** — the existing `PydanticValidatorPipeline` retry loop.

```python
from pydantic import BaseModel
from pirn_agents.specializations.structured_output import structured_decode

class Invoice(BaseModel):
    vendor: str
    amount: float

# `my_llm` is any LLMProvider. If it implements the StructuredOutputProvider
# surface (the shipped OpenAI-compatible / Messages providers do), the best
# native path is used; a plain provider transparently routes to the retry
# pipeline. Provider-neutral — no vendor is named or privileged.
invoice = await structured_decode(prompt="Extract the invoice", llm=my_llm,
                                  model_class=Invoice, max_retries=3)
```

**Capability gating is provider-owned**: a provider advertises flags
(`native_schema` / `forced_tool_choice` / `constrained_decoding`) and shapes each
native request behind its own boundary, so the decoder stays provider-neutral.
The shipped chat-completions provider advertises all three; the Messages
provider advertises forced tool-choice only.

---

## Anti-patterns

**Setting `max_retries=0`** — without retries, any format error produces an immediate `Err`. LLMs frequently mis-format on the first attempt; set at least `max_retries=2`.

**Using `YamlExtractorPipeline` for deeply nested objects** — YAML indentation errors are common in LLM output for deep structures. Use `JsonExtractorPipeline` or `PydanticValidatorPipeline` for complex schemas.

---

## Constraints and gotchas

- **`PydanticValidatorPipeline` requires Pydantic v2.** v1 model classes are not supported.
- **`RetryOnParseFailure` includes the error message in the re-prompt.** Do not expose internal schema details if the prompt is user-visible.
- **`EnumClassifierPipeline` normalizes LLM output to lowercase before matching.** Enum values must be lowercase strings for reliable matching.
- **All pipelines return the typed Python value (not the raw LLM text)** on success, or `Err` after exhausting retries.

---

## Quick reference

| Output type | Pipeline |
|-------------|---------|
| Pydantic model | `PydanticValidatorPipeline(model=MyModel, ...)` |
| JSON dict (with schema) | `JsonExtractorPipeline(schema={...}, ...)` |
| YAML dict | `YamlExtractorPipeline(...)` |
| Enum value | `EnumClassifierPipeline(target_enum=MyEnum, ...)` |
| Custom format + retry | `RetryOnParseFailure(extractor=..., max_retries=N)` |
| Native single-pass (auto-fallback) | `await structured_decode(prompt=..., llm=..., model_class=MyModel)` |

---

*See also: [specializations AGENTIC_USE.md](../AGENTIC_USE.md)*
