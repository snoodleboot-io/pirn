`pirn.domains.agents.specializations.specialized_agents` provides complete, end-to-end pre-built agents for common tasks — it does not wire these agents into a larger system automatically; you must connect their inputs and outputs to your tapestry.

---

## Mental model

Each specialized agent is a self-contained pipeline knot: one input (a request or question), one output (a result). Internally, each agent combines tool use, memory, structured output, and LLM calls as appropriate for its domain. Use them as drop-in building blocks within a larger tapestry.

The tradeoff vs. custom assembly: specialized agents are fast to wire but less configurable. If you need to customize prompts, swap tools, or change retrieval strategy, build from stage knots instead.

---

## Source map

```
pirn/domains/agents/specializations/specialized_agents/
├── research_agent.py        ResearchAgent       — multi-hop web search + synthesis; returns a research report
├── browser_agent.py         BrowserAgent        — navigates web pages; extracts structured data from HTML
├── code_agent.py            CodeAgent           — generates, lints, and formats code given a specification
├── sql_agent.py             SqlAgent            — text-to-SQL; executes query; returns formatted results
├── data_analyst_agent.py    DataAnalystAgent    — statistical analysis + chart description over tabular data
│
│  ── Internal helpers ──
├── _analysis_step.py        (internal — single analysis step for DataAnalystAgent)
├── _code_generator.py       (internal — LLM code generation call)
├── _code_linter.py          (internal — lint generated code before returning)
├── _code_response_formatter.py (internal — format code output with language tag)
├── _sql_generator.py        (internal — text-to-SQL LLM call)
├── _sql_executor.py         (internal — execute SQL against pool; return rows)
└── _sql_response_formatter.py  (internal — format SQL result as markdown table)
```

---

## Canonical pattern

### SQL agent — natural language to query to result

```python
from pirn.domains.agents.specializations.specialized_agents.sql_agent import SqlAgent
from pirn import Tapestry, Parameter, KnotConfig, RunRequest

with Tapestry() as t:
    question = Parameter("question", str)
    result   = SqlAgent(
        question=question,
        schema=my_db_schema_str,   # DDL string describing tables
        pool=my_postgres_pool,
        llm=my_llm,
        _config=KnotConfig(id="sql-agent"),
    )

result = await t.run(RunRequest(parameters={"question": "How many orders were placed last week?"}))
```

### Code agent — generate and lint code

```python
from pirn.domains.agents.specializations.specialized_agents.code_agent import CodeAgent

with Tapestry() as t:
    spec = Parameter("spec", str)
    code = CodeAgent(
        spec=spec,
        language="python",
        llm=my_llm,
        _config=KnotConfig(id="code-agent"),
    )
```

### Research agent — multi-hop web research

```python
from pirn.domains.agents.specializations.specialized_agents.research_agent import ResearchAgent

with Tapestry() as t:
    topic  = Parameter("topic", str)
    report = ResearchAgent(
        topic=topic,
        search_tool=my_web_search_tool,
        llm=my_llm,
        max_hops=5,
        _config=KnotConfig(id="research"),
    )
```

---

## Anti-patterns

**Using `SqlAgent` without providing a schema** — the LLM cannot generate correct SQL without knowing table names and columns. Pass a full DDL string or a compact schema description.

**Using `BrowserAgent` for structured data extraction from APIs** — `BrowserAgent` navigates and scrapes HTML. For REST API data, use the appropriate SaaS client from `pirn.domains.connectors.saas` instead.

---

## Constraints and gotchas

- **`SqlAgent` executes generated SQL directly against the pool.** Run with a read-only database user for safety — the agent does not sandbox the generated query.
- **`ResearchAgent` makes `max_hops` sequential LLM + search calls.** Latency scales linearly with `max_hops`. Default is `3`.
- **`CodeAgent` lints output using the language's default linter** (`ruff` for Python, `eslint` for JavaScript). The linter must be installed in the environment.
- **`DataAnalystAgent` returns a text description of charts**, not rendered images. Pair with a charting knot if visual output is needed.

---

## Quick reference

| Task | Agent |
|------|-------|
| Multi-hop web research report | `ResearchAgent(topic=..., search_tool=..., llm=...)` |
| Web page navigation + extraction | `BrowserAgent(url=..., task=..., llm=...)` |
| Code generation + linting | `CodeAgent(spec=..., language=..., llm=...)` |
| Natural language SQL query | `SqlAgent(question=..., schema=..., pool=..., llm=...)` |
| Statistical analysis over table | `DataAnalystAgent(data=..., question=..., llm=...)` |

---

*See also: [specializations AGENTIC_USE.md](../AGENTIC_USE.md)*
