"""``CodeAgent`` — code generation with linting and stubbed test execution.

A :class:`SubTapestry` that asks the LLM to emit code for a given task in
a target programming language. The generated code is returned via
``content`` on the :class:`AgentResponse`.

Test execution is intentionally stubbed: real test execution is sandbox-
sensitive (it requires a hermetic build environment, a language-specific
runner, and resource limits) and lives outside the scope of this knot.
The pipeline emits a stubbed ``"tests: skipped (stub)"`` line in the
response usage block to make the punt explicit downstream.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.specialized_agents._code_generator import (  # noqa: E501
    _CodeGenerator,
)
from pirn.domains.agents.specializations.specialized_agents._code_linter import (
    _CodeLinter,
)
from pirn.domains.agents.specializations.specialized_agents._code_response_formatter import (  # noqa: E501
    _CodeResponseFormatter,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class CodeAgent(SubTapestry):
    """LLM code generation with lint pass; test execution is stubbed."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: LLMProvider,
        _config: KnotConfig,
        language: str = "python",
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "CodeAgent: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(language, str) or not language:
            raise TypeError(
                "CodeAgent: language must be a non-empty string, "
                f"got {language!r}"
            )
        self._llm = llm
        self._language = language
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str, **_: Any) -> AgentResponse:
        if not isinstance(task, str) or not task:
            raise TypeError(
                "CodeAgent: task must be a non-empty string, "
                f"got {task!r}"
            )
        with Tapestry() as inner:
            code = _CodeGenerator(
                task=task,
                llm=self._llm,
                language=self._language,
                _config=KnotConfig(id="generate_code"),
            )
            warnings = _CodeLinter(
                code=code,
                language=self._language,
                _config=KnotConfig(id="lint_code"),
            )
            _CodeResponseFormatter(
                code=code,
                warnings=warnings,
                _config=KnotConfig(id="format_response"),
            )
        inner_result = await self._run_inner(inner)
        response = inner_result.outputs.get("format_response")
        if not isinstance(response, AgentResponse):
            return AgentResponse(content="", finish_reason="length")
        return response
