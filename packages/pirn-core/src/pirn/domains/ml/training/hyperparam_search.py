"""``HyperparamSearch`` — grid / random / bayesian search over an
algorithm's hyperparameter space.

This orchestration-layer knot picks the first candidate from the search
space (deterministic given the seed) and emits a :class:`ModelManifest`
reference. Concrete subclasses can override :meth:`_score_candidate` to
plug in a real fit/score loop; the base class returns a constant score
for every candidate so the search remains well-defined offline.

Algorithm:
    1. Receive split, algorithm, search_space, strategy, n_trials, and random_seed via process().
    2. Validate all inputs.
    3. Enumerate candidates (grid: all combos; random/bayesian: shuffled sample up to n_trials).
    4. Score each candidate via _score_candidate (deterministic hash in base class).
    5. Select the highest-scoring candidate and derive a model_id.
    6. Return a ModelManifest for the best candidate.

Math:
    candidate_score = sha256(random_seed || candidate)[0:8] as uint64 / 2^64
    model_id = "<algorithm>:<strategy>:" + sha256(algorithm || candidate || strategy || split)[0:16]

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest


class HyperparamSearch(Knot):
    """Emit the best :class:`ModelManifest` from an enumerated search space."""

    valid_strategies: ClassVar[frozenset[str]] = frozenset({"grid", "random", "bayesian"})

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: Knot | str,
        search_space: Knot | Mapping[str, Sequence[Any]],
        strategy: Knot | str = "grid",
        n_trials: Knot | int = 10,
        random_seed: Knot | int = 42,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            algorithm=algorithm,
            search_space=search_space,
            strategy=strategy,
            n_trials=n_trials,
            random_seed=random_seed,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        algorithm: str,
        search_space: Mapping[str, Sequence[Any]],
        strategy: str = "grid",
        n_trials: int = 10,
        random_seed: int = 42,
        **_: Any,
    ) -> ModelManifest:
        """Enumerate and score candidates from the search space using the configured strategy and return the best ModelManifest.

        Args:
            split: SplitManifest whose train partition metadata is used to derive
                the deterministic model_id for the winning candidate.
            algorithm: Non-empty algorithm name string.
            search_space: Non-empty mapping of hyperparameter name to candidate values.
            strategy: Search strategy; must be one of ``valid_strategies``.
            n_trials: Maximum candidates to evaluate (for random/bayesian); must be >= 1.
            random_seed: Seed for deterministic candidate shuffling.

        Returns:
            ModelManifest for the highest-scoring candidate hyperparameter set.

        Raises:
            ValueError: If inputs fail validation.
            TypeError: If n_trials or random_seed are not ints.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("HyperparamSearch: algorithm must be a non-empty string")
        if not isinstance(search_space, Mapping) or not search_space:
            raise ValueError("HyperparamSearch: search_space must be a non-empty Mapping")
        for name, values in search_space.items():
            if not isinstance(name, str) or not name:
                raise ValueError("HyperparamSearch: search_space keys must be non-empty strings")
            if not isinstance(values, Sequence) or isinstance(values, str):
                raise TypeError(
                    f"HyperparamSearch: search_space[{name!r}] must be a non-string Sequence"
                )
            if len(values) == 0:
                raise ValueError(f"HyperparamSearch: search_space[{name!r}] must be non-empty")
        if strategy not in self.valid_strategies:
            raise ValueError(
                f"HyperparamSearch: strategy must be one of {sorted(self.valid_strategies)}"
            )
        if not isinstance(n_trials, int):
            raise TypeError("HyperparamSearch: n_trials must be an int")
        if n_trials < 1:
            raise ValueError("HyperparamSearch: n_trials must be >= 1")
        if not isinstance(random_seed, int):
            raise TypeError("HyperparamSearch: random_seed must be an int")
        frozen_space = MappingProxyType({k: tuple(v) for k, v in search_space.items()})
        candidates = self._enumerate(frozen_space, strategy, n_trials, random_seed)
        best = self._best_candidate(candidates, random_seed)
        model_id = self._derive_model_id(split, best, algorithm, strategy)
        return ModelManifest(
            model_id=model_id,
            algorithm=algorithm,
            hyperparameters=MappingProxyType(dict(best)),
            feature_names=split.train.feature_names,
            target_name=split.train.target_name,
            created_at=datetime.now(UTC),
        )

    def _enumerate(
        self,
        search_space: MappingProxyType,  # type: ignore[type-arg]
        strategy: str,
        n_trials: int,
        random_seed: int,
    ) -> list[dict[str, Any]]:
        names = list(search_space.keys())
        value_lists = [list(search_space[n]) for n in names]
        if strategy == "grid":
            return [
                dict(zip(names, combo, strict=False)) for combo in itertools.product(*value_lists)
            ]
        # random + bayesian both walk the cartesian product up to n_trials,
        # the bayesian variant additionally shuffles to a deterministic order.
        rng = random.Random(random_seed)
        full = [dict(zip(names, combo, strict=False)) for combo in itertools.product(*value_lists)]
        rng.shuffle(full)
        return full[:n_trials]

    def _best_candidate(self, candidates: list[dict[str, Any]], random_seed: int) -> dict[str, Any]:
        # Score every candidate; pick the one with the highest score.
        # Subclasses override _score_candidate to plug in real metrics.
        scored = [(self._score_candidate(c, random_seed), c) for c in candidates]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored[0][1]

    def _score_candidate(self, candidate: Mapping[str, Any], random_seed: int) -> float:
        """Default scoring: deterministic hash, seeded by random_seed.

        Real subclasses fit a model on the train split and score it on
        the validation split.
        """
        payload = json.dumps(
            {"seed": random_seed, "candidate": dict(candidate)},
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)

    def _derive_model_id(
        self, split: SplitManifest, candidate: Mapping[str, Any], algorithm: str, strategy: str
    ) -> str:
        payload = json.dumps(
            {
                "algorithm": algorithm,
                "candidate": dict(candidate),
                "strategy": strategy,
                "train_name": split.train.name,
                "train_row_count": split.train.row_count,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{algorithm}:{strategy}:{digest[:16]}"
