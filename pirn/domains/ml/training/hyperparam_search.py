"""``HyperparamSearch`` — grid / random / bayesian search over an
algorithm's hyperparameter space.

This orchestration-layer knot picks the first candidate from the search
space (deterministic given the seed) and emits a :class:`TrainedModel`
reference. Concrete subclasses can override :meth:`_score_candidate` to
plug in a real fit/score loop; the base class returns a constant score
for every candidate so the search remains well-defined offline.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, ClassVar, Mapping, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel


class HyperparamSearch(Knot):
    """Emit the best :class:`TrainedModel` from an enumerated search space."""

    valid_strategies: ClassVar[frozenset[str]] = frozenset(
        {"grid", "random", "bayesian"}
    )

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: str,
        search_space: Mapping[str, Sequence[Any]],
        strategy: str = "grid",
        n_trials: int = 10,
        random_seed: int = 42,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "HyperparamSearch: algorithm must be a non-empty string"
            )
        if not isinstance(search_space, Mapping) or not search_space:
            raise ValueError(
                "HyperparamSearch: search_space must be a non-empty Mapping"
            )
        for name, values in search_space.items():
            if not isinstance(name, str) or not name:
                raise ValueError(
                    "HyperparamSearch: search_space keys must be non-empty "
                    "strings"
                )
            if not isinstance(values, Sequence) or isinstance(values, str):
                raise TypeError(
                    f"HyperparamSearch: search_space[{name!r}] must be a "
                    "non-string Sequence"
                )
            if len(values) == 0:
                raise ValueError(
                    f"HyperparamSearch: search_space[{name!r}] must be "
                    "non-empty"
                )
        if strategy not in self.valid_strategies:
            raise ValueError(
                f"HyperparamSearch: strategy must be one of "
                f"{sorted(self.valid_strategies)}"
            )
        if not isinstance(n_trials, int):
            raise TypeError("HyperparamSearch: n_trials must be an int")
        if n_trials < 1:
            raise ValueError("HyperparamSearch: n_trials must be >= 1")
        if not isinstance(random_seed, int):
            raise TypeError("HyperparamSearch: random_seed must be an int")
        self._algorithm = algorithm
        self._search_space = MappingProxyType(
            {k: tuple(v) for k, v in search_space.items()}
        )
        self._strategy = strategy
        self._n_trials = n_trials
        self._random_seed = random_seed
        super().__init__(split=split, _config=_config, **kwargs)

    @property
    def strategy(self) -> str:
        return self._strategy

    async def process(self, split: DataSplit, **_: Any) -> TrainedModel:
        """Enumerate and score candidates from the search space using the configured strategy and return the best TrainedModel.

        Args:
            split: DataSplit whose train partition metadata is used to derive
                the deterministic model_id for the winning candidate.

        Returns:
            TrainedModel for the highest-scoring candidate hyperparameter set.
        """
        candidates = self._enumerate()
        best = self._best_candidate(candidates)
        model_id = self._derive_model_id(split, best)
        return TrainedModel(
            model_id=model_id,
            algorithm=self._algorithm,
            hyperparameters=MappingProxyType(dict(best)),
            feature_names=split.train.feature_names,
            target_name=split.train.target_name,
            created_at=datetime.now(timezone.utc),
        )

    def _enumerate(self) -> list[dict[str, Any]]:
        names = list(self._search_space.keys())
        value_lists = [list(self._search_space[n]) for n in names]
        if self._strategy == "grid":
            return [
                dict(zip(names, combo))
                for combo in itertools.product(*value_lists)
            ]
        # random + bayesian both walk the cartesian product up to n_trials,
        # the bayesian variant additionally shuffles to a deterministic order.
        rng = random.Random(self._random_seed)
        full = [
            dict(zip(names, combo))
            for combo in itertools.product(*value_lists)
        ]
        rng.shuffle(full)
        return full[: self._n_trials]

    def _best_candidate(
        self, candidates: list[dict[str, Any]]
    ) -> dict[str, Any]:
        # Score every candidate; pick the one with the highest score.
        # Subclasses override _score_candidate to plug in real metrics.
        scored = [(self._score_candidate(c), c) for c in candidates]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored[0][1]

    def _score_candidate(self, candidate: Mapping[str, Any]) -> float:
        """Default scoring: deterministic hash, seeded by random_seed.

        Real subclasses fit a model on the train split and score it on
        the validation split.
        """
        payload = json.dumps(
            {"seed": self._random_seed, "candidate": dict(candidate)},
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)

    def _derive_model_id(
        self, split: DataSplit, candidate: Mapping[str, Any]
    ) -> str:
        payload = json.dumps(
            {
                "algorithm": self._algorithm,
                "candidate": dict(candidate),
                "strategy": self._strategy,
                "train_name": split.train.name,
                "train_row_count": split.train.row_count,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{self._algorithm}:{self._strategy}:{digest[:16]}"
