"""``DeterministicRng`` — a seeded, injectable source of randomness for a run."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Sequence
from typing import TypeVar

_T = TypeVar("_T")


class DeterministicRng:
    """A reproducible RNG wrapping :class:`random.Random`, seeded per run.

    Nothing in a deterministic run may call the global ``random`` module; each
    source of randomness is drawn from an injected ``DeterministicRng``. Given the
    same ``seed`` the stream is identical across processes and machines, so two
    runs with the same seed produce byte-identical output. :meth:`fork` derives a
    named child stream deterministically for independent sub-components.
    """

    def __init__(self, *, seed: int) -> None:
        """Initialise the RNG from integer ``seed``.

        Raises:
            TypeError: If ``seed`` is not an int.
        """
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise TypeError(f"DeterministicRng: seed must be an int, got {type(seed).__name__}")
        self._seed = seed
        self._random = random.Random(seed)

    @property
    def seed(self) -> int:
        """Return the integer seed this stream was created from."""
        return self._seed

    def random(self) -> float:
        """Return the next float in ``[0.0, 1.0)`` from the reproducible stream."""
        return self._random.random()

    def randint(self, low: int, high: int) -> int:
        """Return a reproducible integer in the inclusive range ``[low, high]``."""
        return self._random.randint(low, high)

    def choice(self, items: Sequence[_T]) -> _T:
        """Return a reproducibly chosen element of non-empty ``items``.

        Raises:
            IndexError: If ``items`` is empty.
        """
        if len(items) == 0:
            raise IndexError("DeterministicRng.choice: cannot choose from an empty sequence")
        return items[self._random.randrange(len(items))]

    def fork(self, label: str) -> DeterministicRng:
        """Return a child RNG whose seed is derived from this seed and ``label``.

        The derivation is a stable hash of ``(seed, label)``, so sub-components
        get independent but reproducible streams without sharing this one's state.
        """
        digest = hashlib.sha256(f"{self._seed}:{label}".encode()).digest()
        child_seed = int.from_bytes(digest[:8], "big")
        return DeterministicRng(seed=child_seed)
