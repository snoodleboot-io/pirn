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
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class _CodeGenerator(Knot):
    """Ask the LLM to emit code for the supplied task."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: LLMProvider,
        language: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._llm = llm
        self._language = language
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str, **_: Any) -> str:
        if not isinstance(task, str) or not task:
            raise TypeError(
                "CodeAgent: task must be a non-empty string, "
                f"got {task!r}"
            )
        chat_messages = [
            {
                "role": "system",
                "content": (
                    f"You are a senior {self._language} engineer. Reply with "
                    f"working {self._language} code only — no prose, no "
                    "markdown fences, no explanation."
                ),
            },
            {"role": "user", "content": task},
        ]
        raw = await self._llm.chat(chat_messages)
        return _extract_text(raw)


class _CodeLinter(Knot):
    """Apply lightweight structural checks to the generated code."""

    def __init__(
        self,
        *,
        code: Knot,
        language: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._language = language
        super().__init__(code=code, _config=_config, **kwargs)

    async def process(self, code: str, **_: Any) -> list[str]:
        warnings: list[str] = []
        if not code.strip():
            warnings.append("generated code is empty")
        if "```" in code:
            warnings.append("generated code contains markdown fences")
        if self._language.lower() == "python":
            try:
                import ast

                ast.parse(code)
            except SyntaxError as exc:
                warnings.append(f"python syntax error: {exc.msg}")
        return warnings


class _CodeResponseFormatter(Knot):
    """Wrap the code plus linter warnings into an :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        code: Knot,
        warnings: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            code=code,
            warnings=warnings,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        code: str,
        warnings: list[str],
        **_: Any,
    ) -> AgentResponse:
        usage: dict[str, int] = {
            "lint_warnings": len(warnings),
            "tests_skipped": 1,
        }
        return AgentResponse(
            content=code,
            finish_reason="stop",
            usage=usage,
        )


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
