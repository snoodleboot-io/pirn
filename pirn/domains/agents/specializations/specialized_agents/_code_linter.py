"""``_CodeLinter`` — internal helper Knot for :class:`CodeAgent`.

Applies lightweight structural checks (empty body, leftover markdown
fences, ``ast.parse`` for Python) to the generated code. Internal API.

Algorithm:
    1. Receive the generated ``code`` string and target ``language``.
    2. Warn if the stripped code is empty.
    3. Warn if the code contains markdown fence markers (````).
    4. For Python only: attempt ``ast.parse``; append a warning on
       :class:`SyntaxError`.
    5. Return the (possibly empty) list of warning strings.

Math:
    No numeric computation.

References:
    - Python ``ast`` module: https://docs.python.org/3/library/ast.html
"""

from __future__ import annotations

import ast
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class _CodeLinter(Knot):
    """Apply lightweight structural checks to the generated code."""

    def __init__(
        self,
        *,
        code: Knot | str,
        language: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(code=code, language=language, _config=_config, **kwargs)

    async def process(self, code: str, language: str, **_: Any) -> list[str]:
        """Check the generated code for structural issues and return a list of warning strings.

        Args:
            code: The generated code string to inspect for structural issues.
            language: The target programming language used to decide whether to parse syntax.

        Returns:
            A list of warning strings; empty when no issues are detected.
        """
        warnings: list[str] = []
        if not code.strip():
            warnings.append("generated code is empty")
        if "```" in code:
            warnings.append("generated code contains markdown fences")
        if language.lower() == "python":
            try:
                ast.parse(code)
            except SyntaxError as exc:
                warnings.append(f"python syntax error: {exc.msg}")
        return warnings
