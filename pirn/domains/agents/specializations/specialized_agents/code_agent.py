"""``CodeAgent`` — code generation with linting and stubbed test execution.

A :class:`SubTapestry` that asks the LLM to emit code for a given task in
a target programming language. The generated code is returned via
``content`` on the :class:`AgentResponse`.

Test execution is intentionally stubbed: real test execution is sandbox-
sensitive (it requires a hermetic build environment, a language-specific
runner, and resource limits) and lives outside the scope of this knot.
The pipeline emits a stubbed ``"tests: skipped (stub)"`` line in the
response usage block to make the punt explicit downstream.

Algorithm:
    1. Receive ``task`` (str) and ``language`` (str) as plain values.
    2. Validate that ``task`` is a non-empty string.
    3. Build an inner :class:`Tapestry` containing :class:`_CodeGenerator`,
       :class:`_CodeLinter`, and :class:`_CodeResponseFormatter`.
    4. Run the inner tapestry and extract the ``AgentResponse`` output.

Math:
    None.

References:
    None.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.specialized_agents._code_generator import (
    _CodeGenerator,
)
from pirn.domains.agents.specializations.specialized_agents._code_linter import (
    _CodeLinter,
)
from pirn.domains.agents.specializations.specialized_agents._code_response_formatter import (
    _CodeResponseFormatter,
)
from pirn.nodes.sub_tapestry import SubTapestry


class CodeAgent(SubTapestry):
    """LLM code generation with lint pass; test execution is stubbed."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        language: Knot | str = "python",
        **kwargs: Any,
    ) -> None:
        super().__init__(task=task, llm=llm, language=language, _config=_config, **kwargs)

    async def process(self, task: str, llm: LLMProvider, language: str = "python", **_: Any) -> Any:
        """Generate code for the task, run a lint pass, and return the formatted AgentResponse.

        Args:
            task: The non-empty task description used to prompt the LLM for code.
            llm: The LLM provider to use for code generation.
            language: The target programming language (default: "python").

        Returns:
            An AgentResponse whose content is the generated code with lint metadata in usage.

        Raises:
            TypeError: If task is not a non-empty string, llm is not an LLMProvider,
                or language is not a non-empty string.
        """
        if not isinstance(task, str) or not task:
            raise TypeError(f"CodeAgent: task must be a non-empty string, got {task!r}")
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"CodeAgent: llm must be an LLMProvider, got {type(llm).__name__}")
        if not isinstance(language, str) or not language:
            raise TypeError(f"CodeAgent: language must be a non-empty string, got {language!r}")
        code = _CodeGenerator(
            task=task,
            llm=llm,
            language=language,
            _config=KnotConfig(id="generate_code"),
        )
        warnings = _CodeLinter(
            code=code,
            language=language,
            _config=KnotConfig(id="lint_code"),
        )
        return _CodeResponseFormatter(
            code=code,
            warnings=warnings,
            _config=KnotConfig(id="format_response"),
        )
