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

---

*See also: [specializations AGENTIC_USE.md](../AGENTIC_USE.md)*
