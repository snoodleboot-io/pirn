"""``SQLAgent`` — natural-language to SQL with safe execution.

A :class:`SubTapestry` that asks an LLM to translate a natural-language
question into a SQL query, validates the query through two independent
guards, executes it, and returns the result inside an
:class:`AgentResponse`.

The query is written by a model, so both guards apply and they cover
different threats:

* the **read-only guard** (default, ``read_only=True``) rejects any
  statement that is not a single ``SELECT``/``WITH``, so a model that
  emits ``DROP TABLE``, ``UPDATE`` or DDL is refused before the statement
  reaches the database. Writing is opt-in and explicit (PIR-817);
* the **inline-interpolation guard** rejects ``str.format``-style
  ``{...}`` and printf-style ``%s``/``%d`` markers in the generated SQL,
  defending against both prompt-injected dynamic SQL and accidental bad
  templating from the LLM. It applies in both modes.

Neither guard is a substitute for a least-privilege database role; see
``pirn_agents/TOOLS.md``.

Algorithm:
    1. Receive ``question`` (str), ``llm``, ``pool``, and
       ``schema_description`` as plain values.
    2. Validate that ``question`` is a non-empty string.
    3. Build an inner :class:`Tapestry` containing :class:`_SQLGenerator`,
       :class:`_SQLExecutor`, and :class:`_SQLResponseFormatter`.
    4. Run the inner tapestry and extract the ``AgentResponse`` output.

Math:
    None.

References:
    None.
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.specialized_agents._sql_executor import (
    _SQLExecutor,
)
from pirn_agents.specializations.specialized_agents._sql_generator import (
    _SQLGenerator,
)
from pirn_agents.specializations.specialized_agents._sql_response_formatter import (
    _SQLResponseFormatter,
)


class SQLAgent(AgentPipeline):
    """Translate natural language to SQL, execute, return :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        question: Knot | str,
        llm: Knot | LLMProvider,
        pool: Knot | DatabaseConnectionPool,
        _config: KnotConfig,
        schema_description: Knot | str = "",
        read_only: bool = True,
        **kwargs: Any,
    ) -> None:
        """Bind the question, providers, and the write policy for generated SQL.

        Args:
            question: The natural-language question, or the knot producing it.
            llm: The LLM provider, or the knot producing it.
            pool: The database connection pool, or the knot producing it.
            _config: Framework knot configuration.
            schema_description: Optional schema hint passed to the LLM.
            read_only: When ``True`` (the default), the generated statement must
                be a single ``SELECT``/``WITH``; anything else is refused before
                it reaches the database. Set ``False`` only where this agent is
                genuinely meant to write — the statement is model-written, so
                writing is opt-in and explicit (PIR-817).

        Note:
            ``read_only`` is held as plain constructor state rather than being
            forwarded as a knot input, so the policy cannot be driven by another
            knot's output on a pipeline whose data originates in model text.
        """
        self._read_only = read_only
        super().__init__(
            question=question,
            llm=llm,
            pool=pool,
            schema_description=schema_description,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        question: str,
        llm: LLMProvider,
        pool: DatabaseConnectionPool,
        schema_description: str = "",
        **_: Any,
    ) -> Any:
        """Translate the question to SQL, execute it, and return the result as an AgentResponse.

        Args:
            question: The non-empty natural-language question to translate into SQL and execute.
            llm: The LLM provider used to generate SQL.
            pool: The database connection pool used to execute the SQL.
            schema_description: Optional schema hint passed to the LLM.

        Returns:
            An AgentResponse whose content contains the SQL query and fetched rows.

        Raises:
            TypeError: If question is not a non-empty string, llm is not an LLMProvider,
                pool is not a DatabaseConnectionPool, or schema_description is not a string.
        """
        if not isinstance(question, str) or not question:
            raise TypeError(f"SQLAgent: question must be a non-empty string, got {question!r}")
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"SQLAgent: llm must be an LLMProvider, got {type(llm).__name__}")
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                f"SQLAgent: pool must be a DatabaseConnectionPool, got {type(pool).__name__}"
            )
        if not isinstance(schema_description, str):
            raise TypeError(
                "SQLAgent: schema_description must be a string, "
                f"got {type(schema_description).__name__}"
            )
        sql = _SQLGenerator(
            question=question,
            llm=llm,
            schema_description=schema_description,
            _config=KnotConfig(id="generate_sql"),
        )
        rows = _SQLExecutor(
            sql=sql,
            pool=pool,
            read_only=self._read_only,
            _config=KnotConfig(id="execute_sql"),
        )
        return _SQLResponseFormatter(
            sql=sql,
            rows=rows,
            _config=KnotConfig(id="format_response"),
        )
