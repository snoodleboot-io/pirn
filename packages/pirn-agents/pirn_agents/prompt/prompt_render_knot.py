"""``PromptRenderKnot`` — render a :class:`PromptTemplate` inside the graph.

Algorithm:
    1. Receive the resolved ``template`` and ``variables``.
    2. Validate input types at process time.
    3. Delegate to :meth:`PromptTemplate.render` for injection-safe substitution.
    4. Return the rendered prompt string.


References:
    - :class:`pirn_agents.prompt.prompt_template.PromptTemplate`
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.prompt.prompt_template import PromptTemplate


class PromptRenderKnot(Knot):
    """Renders a :class:`PromptTemplate` with a mapping of variables."""

    def __init__(
        self,
        *,
        template: Knot | PromptTemplate,
        _config: KnotConfig,
        variables: Knot | Mapping[str, Any] = {},  # noqa: B006 — resolved by the graph, never mutated
        strict: Knot | bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            template=template,
            variables=variables,
            strict=strict,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        template: PromptTemplate,
        variables: Mapping[str, Any],
        strict: bool = True,
        **_: Any,
    ) -> str:
        """Render ``template`` with ``variables`` and return the prompt text.

        Args:
            template: The prompt template to render.
            variables: Values keyed by slot name.
            strict: Whether to enforce strict-mode render safety.

        Returns:
            The rendered prompt string.

        Raises:
            TypeError: If ``template`` is not a PromptTemplate or ``variables``
                is not a mapping.
            PromptRenderError: On any strict-mode render failure.
        """
        if not isinstance(template, PromptTemplate):
            raise TypeError(
                "PromptRenderKnot: template must be a PromptTemplate, "
                f"got {type(template).__name__}"
            )
        if not isinstance(variables, Mapping):
            raise TypeError(
                f"PromptRenderKnot: variables must be a mapping, got {type(variables).__name__}"
            )
        return template.render(variables, strict=bool(strict))
