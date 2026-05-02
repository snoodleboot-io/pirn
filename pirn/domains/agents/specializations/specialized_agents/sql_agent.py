"""``SQLAgent`` — natural-language to SQL with safe execution.

A :class:`SubTapestry` that asks an LLM to translate a natural-language
question into a SQL query, validates the query through the connector
pool's ``_reject_inline_interpolation`` guard, executes the query, and
returns the result inside an :class:`AgentResponse`.

The inline-interpolation guard rejects ``str.format``-style ``{...}`` and
printf-style ``%s``/``%d`` markers in the generated SQL, defending
against both prompt-injected dynamic SQL and accidental bad templating
from the LLM.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.specialized_agents._sql_executor import (
    _SQLExecutor,
)
from pirn.domains.agents.specializations.specialized_agents._sql_generator import (
    _SQLGenerator,
)
from pirn.domains.agents.specializations.specialized_agents._sql_response_formatter import (  # noqa: E501
    _SQLResponseFormatter,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class SQLAgent(SubTapestry):
    """Translate natural language to SQL, execute, return :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        question: Knot | str,
        llm: LLMProvider,
        pool: DatabaseConnectionPool,
        _config: KnotConfig,
        schema_description: str = "",
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "SQLAgent: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "SQLAgent: pool must be a DatabaseConnectionPool, "
                f"got {type(pool).__name__}"
            )
        if not isinstance(schema_description, str):
            raise TypeError(
                "SQLAgent: schema_description must be a string, "
                f"got {type(schema_description).__name__}"
            )
        self._llm = llm
        self._pool = pool
        self._schema_description = schema_description
        super().__init__(question=question, _config=_config, **kwargs)

    async def process(self, question: str, **_: Any) -> AgentResponse:
        if not isinstance(question, str) or not question:
            raise TypeError(
                "SQLAgent: question must be a non-empty string, "
                f"got {question!r}"
            )
        with Tapestry() as inner:
            sql = _SQLGenerator(
                question=question,
                llm=self._llm,
                schema_description=self._schema_description,
                _config=KnotConfig(id="generate_sql"),
            )
            rows = _SQLExecutor(
                sql=sql,
                pool=self._pool,
                _config=KnotConfig(id="execute_sql"),
            )
            _SQLResponseFormatter(
                sql=sql,
                rows=rows,
                _config=KnotConfig(id="format_response"),
            )
        inner_result = await self._run_inner(inner)
        response = inner_result.outputs.get("format_response")
        if not isinstance(response, AgentResponse):
            return AgentResponse(content="", finish_reason="length")
        return response
