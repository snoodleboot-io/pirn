"""``_CodeLinter`` — internal helper Knot for :class:`CodeAgent`.

Applies lightweight structural checks (empty body, leftover markdown
fences, ``ast.parse`` for Python) to the generated code. Internal API.
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
                ast.parse(code)
            except SyntaxError as exc:
                warnings.append(f"python syntax error: {exc.msg}")
        return warnings
