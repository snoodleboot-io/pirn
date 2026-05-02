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
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class _SQLGenerator(Knot):
    """Ask the LLM to emit a single SQL statement for the question."""

    def __init__(
        self,
        *,
        question: Knot | str,
        llm: LLMProvider,
        schema_description: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._llm = llm
        self._schema_description = schema_description
        super().__init__(question=question, _config=_config, **kwargs)

    async def process(self, question: str, **_: Any) -> str:
        if not isinstance(question, str) or not question:
            raise TypeError(
                "SQLAgent: question must be a non-empty string, "
                f"got {question!r}"
            )
        system_lines = [
            "You are a SQL writing assistant.",
            "Reply with a single SQL statement only — no commentary, no "
            "fences, no semicolons after the statement.",
            "Use only standard SQL bind syntax (named or positional "
            "parameters); never inline values via Python string "
            "formatting like {value} or %s.",
        ]
        if self._schema_description:
            system_lines.append(
                f"Schema reference:\n{self._schema_description}"
            )
        chat_messages = [
            {"role": "system", "content": "\n".join(system_lines)},
            {"role": "user", "content": question},
        ]
        raw = await self._llm.chat(chat_messages)
        return _extract_text(raw).strip()


class _SQLExecutor(Knot):
    """Validate the SQL through the pool guard and run it."""

    def __init__(
        self,
        *,
        sql: Knot,
        pool: DatabaseConnectionPool,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._pool = pool
        super().__init__(sql=sql, _config=_config, **kwargs)

    async def process(self, sql: str, **_: Any) -> list[Any]:
        if not isinstance(sql, str) or not sql:
            raise ValueError(
                "SQLAgent: generator returned empty SQL"
            )
        # Defends against prompt-injected dynamic SQL and accidental
        # ``str.format`` interpolation in the generated query.
        self._pool._reject_inline_interpolation(sql)
        if hasattr(self._pool, "fetch_all"):
            rows = await self._pool.fetch_all(sql)
        else:
            connection = await self._pool.acquire()
            try:
                cursor = await connection.execute(sql)
                rows = await cursor.fetchall()
            finally:
                await self._pool.release(connection)
        return list(rows)


class _SQLResponseFormatter(Knot):
    """Wrap the SQL plus rows into an :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        sql: Knot,
        rows: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(sql=sql, rows=rows, _config=_config, **kwargs)

    async def process(
        self,
        sql: str,
        rows: list[Any],
        **_: Any,
    ) -> AgentResponse:
        rendered_rows = "\n".join(repr(row) for row in rows)
        content = (
            f"SQL:\n{sql}\n\n"
            f"Rows ({len(rows)}):\n{rendered_rows}"
        )
        return AgentResponse(content=content, finish_reason="stop")


def _extract_text(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        content = raw.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict):
                text = first.get("text")
                if isinstance(text, str):
                    return text
            if isinstance(first, str):
                return first
        text = raw.get("text")
        if isinstance(text, str):
            return text
    return str(raw)


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
