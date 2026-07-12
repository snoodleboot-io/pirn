"""``TokenEstimator`` — the common interface for provider-aware token counting.

Different providers tokenize text differently, so budgeting cannot assume a
single tokenization. A :class:`TokenEstimator` is the pluggable strategy behind
:class:`pirn_agents.context.token_counter.TokenCounter`: each concrete estimator
models one provider's tokenization (a byte-pair encoder, a word-piece encoder,
or a cheap character heuristic). The interface is deliberately tiny —
:meth:`estimate` maps text to an integer token count — so a real encoder can be
dropped in later behind a lazy ``_require``-guarded import + a flat extra without
changing any caller.
"""

from __future__ import annotations

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class TokenEstimator(PirnOpaqueValue):
    """Interface every provider token-estimation strategy must satisfy."""

    @property
    def name(self) -> str:
        """Return the estimator's identity (typically a provider label)."""
        raise NotImplementedError(f"{type(self).__name__} must implement name")

    def estimate(self, text: str) -> int:
        """Return the estimated number of tokens in ``text`` (``0`` when empty)."""
        raise NotImplementedError(f"{type(self).__name__} must implement estimate()")
