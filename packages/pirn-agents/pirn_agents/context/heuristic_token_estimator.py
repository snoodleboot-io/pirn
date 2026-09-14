"""``HeuristicTokenEstimator`` — a backend-free default token estimator.

Estimates tokens as ``ceil(len(text) / chars_per_token)``. The default ratio of
four characters per token approximates common byte-pair encoders closely enough
for budgeting, and — crucially — needs **no** tokenizer backend, so
``import pirn_agents`` stays dependency-free. Provider-awareness is expressed by
constructing the estimator with a provider-specific ``chars_per_token`` (and a
``name`` label); a provider whose real encoder matters can instead supply a
concrete :class:`~pirn_agents.context.token_estimator.TokenEstimator` that
lazily imports its backend.
"""

from __future__ import annotations

from math import ceil

from pirn_agents.context.token_estimator import TokenEstimator


class HeuristicTokenEstimator(TokenEstimator):
    """A character-ratio token estimator requiring no tokenizer backend."""

    def __init__(self, *, name: str = "heuristic", chars_per_token: float = 4.0) -> None:
        """Create a heuristic estimator.

        Args:
            name: Identity label (typically the provider this ratio models).
            chars_per_token: Average characters per token; must be positive.

        Raises:
            TypeError: If ``name`` is not a str.
            ValueError: If ``chars_per_token`` is not a positive number.
        """
        if not isinstance(name, str) or not name:
            raise TypeError("HeuristicTokenEstimator: name must be a non-empty str")
        if not isinstance(chars_per_token, (int, float)) or chars_per_token <= 0:
            raise ValueError(
                "HeuristicTokenEstimator: chars_per_token must be a positive number, "
                f"got {chars_per_token!r}"
            )
        self._name = name
        self._chars_per_token = float(chars_per_token)

    @property
    def name(self) -> str:
        """Return the estimator's identity label."""
        return self._name

    def estimate(self, text: str) -> int:
        """Return ``ceil(len(text) / chars_per_token)`` (``0`` for empty text).

        Raises:
            TypeError: If ``text`` is not a str.
        """
        if not isinstance(text, str):
            raise TypeError(
                f"HeuristicTokenEstimator: text must be a str, got {type(text).__name__}"
            )
        if not text:
            return 0
        return max(1, ceil(len(text) / self._chars_per_token))
