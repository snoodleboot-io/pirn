"""ValueRetention — how many values a data-store backend promises to keep."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ValueRetention(BaseModel):
    """A ``DataStore`` backend's declared retention capability.

    The value-plane counterpart of
    :class:`pirn.backends.base.run_retention.RunRetention`, and it exists for
    the same reason.  ``RunRetention`` answers "can this backend absorb an
    unbounded number of *runs*"; this answers "can it absorb an unbounded
    number of *values*".

    ``LoopSubTapestry`` forces the question on both planes.  It models
    *dynamically extensible* pipelines — conversational flows that run until
    the session ends — so it produces one iteration's worth of values per
    turn, forever.  Until PIR-837 those values went to a throwaway inner
    ``InMemoryDataStore`` that died with the iteration, which bounded memory
    by accident while leaving every inner lineage row pointing at a value
    nobody could fetch.  Forwarding the outer store fixed the dangling
    reference and handed the growth to the outer store, which on the default
    ``InMemoryDataStore`` had no ceiling at all.

    Declaring the capability here is the same inversion PIR-765 made for
    history: the engine never asks what *class* a store is, it asks what the
    store keeps.  A backend that cannot keep everything says so and evicts to
    stay within its ceiling, so an open-ended loop on an ephemeral backend has
    a *bounded* working set rather than an unbounded one.  See PIR-839.

    Attributes:
        max_values: Maximum number of values the backend retains, least
            recently used evicted first once the bound is reached.  ``None``
            means unbounded — the backend is durable and keeps everything
            until it is explicitly scrubbed.
    """

    model_config = ConfigDict(frozen=True)

    max_values: int | None = Field(
        default=None,
        gt=0,
        description="Retained-value ceiling; None for a durable, unbounded backend.",
    )

    @property
    def is_bounded(self) -> bool:
        """True if the backend evicts values to stay within a ceiling."""
        return self.max_values is not None
