"""``SystemPromptComposer`` — deterministically merge layered system prompts.

Algorithm:
    1. Receive the resolved ``layers`` sequence and the ``separator``.
    2. Validate input types at process time.
    3. Drop empty/missing layers.
    4. Order layers by canonical kind rank (persona, policy, tools, memory),
       then by first-seen index so custom layers and equal-rank layers keep a
       stable, documented order.
    5. Render each surviving layer (optional title + content) and join with the
       separator.


References:
    - :class:`pirn_agents.prompt.system_prompt_layer.SystemPromptLayer`
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.prompt.system_prompt_layer import SystemPromptLayer


def _canonical_rank(kind: str) -> int:
    """Return the canonical composition rank for a layer ``kind``.

    The four canonical kinds order deterministically; every other (custom) kind
    shares the trailing rank and falls back to first-seen ordering.
    """
    order = {"persona": 0, "policy": 1, "tools": 2, "memory": 3}
    return order.get(kind, 4)


class SystemPromptComposer(Knot):
    """Composes an ordered system prompt from layered parts.

    The canonical order — persona, then policy, then tools, then memory,
    then any custom layers — is fixed and documented so composition is
    reproducible regardless of the order layers are supplied in. Empty or
    missing layers are skipped without leaving blank sections.
    """

    def __init__(
        self,
        *,
        layers: Knot | Sequence[SystemPromptLayer],
        _config: KnotConfig,
        separator: Knot | str = "\n\n",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            layers=layers,
            separator=separator,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        layers: Sequence[SystemPromptLayer],
        separator: str = "\n\n",
        **_: Any,
    ) -> str:
        """Compose ``layers`` into a single deterministic system-prompt string.

        Args:
            layers: The system-prompt layers to compose, in any order.
            separator: Text joining rendered layers (default a blank line).

        Returns:
            The composed system prompt, or ``""`` when every layer is empty.

        Raises:
            TypeError: If ``layers`` is not a sequence of SystemPromptLayer or
                ``separator`` is not a str.
        """
        if not isinstance(layers, Sequence) or isinstance(layers, (str, bytes)):
            raise TypeError(
                "SystemPromptComposer: layers must be a sequence of "
                f"SystemPromptLayer, got {type(layers).__name__}"
            )
        if not isinstance(separator, str):
            raise TypeError(
                f"SystemPromptComposer: separator must be a str, got {type(separator).__name__}"
            )
        indexed: list[tuple[int, int, SystemPromptLayer]] = []
        for index, layer in enumerate(layers):
            if not isinstance(layer, SystemPromptLayer):
                raise TypeError(
                    f"SystemPromptComposer: layers[{index}] must be a "
                    f"SystemPromptLayer, got {type(layer).__name__}"
                )
            if layer.is_empty():
                continue
            indexed.append((_canonical_rank(layer.kind), index, layer))
        indexed.sort(key=lambda entry: (entry[0], entry[1]))
        return separator.join(self._render_layer(layer) for _, _, layer in indexed)

    @staticmethod
    def _render_layer(layer: SystemPromptLayer) -> str:
        """Render one layer as an optional title followed by trimmed content."""
        body = layer.content.strip()
        if layer.title:
            return f"{layer.title}\n{body}"
        return body
