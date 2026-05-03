"""``EntropyEstimator`` — sample / approximate / permutation entropy."""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class EntropyEstimator(Knot):
    """Time-series complexity / entropy estimator.

    Production needs ``antropy`` / ``EntropyHub`` or a hand-rolled
    implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        entropy_kind: str,
        embedding_dim: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if entropy_kind not in {"sample", "approximate", "permutation", "spectral"}:
            raise ValueError(
                "EntropyEstimator: entropy_kind must be 'sample', 'approximate', "
                "'permutation', or 'spectral'"
            )
        if not isinstance(embedding_dim, int) or embedding_dim <= 0:
            raise ValueError(
                "EntropyEstimator: embedding_dim must be a positive integer"
            )
        self._entropy_kind = entropy_kind
        self._embedding_dim = embedding_dim
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def entropy_kind(self) -> str:
        return self._entropy_kind

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> Mapping[str, Any]:
        """Compute the configured entropy measure from the signal and return an entropy result mapping.

        Args:
            signal: Time series signal to measure entropy from.

        Returns:
            Mapping containing ``signal_id``, ``entropy_kind``, and ``embedding_dim``.
        """
        return {
            "signal_id": signal.signal_id,
            "entropy_kind": self._entropy_kind,
            "embedding_dim": self._embedding_dim,
        }
