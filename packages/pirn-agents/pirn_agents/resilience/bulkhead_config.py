"""``BulkheadConfig`` — deprecated: per-backend concurrency sizing, as a ``ConcurrencyLimits``.

Deprecated (ADR agents-speaks-core, WS4b/PIR-866). Reuses
:class:`~pirn_agents.performance.concurrency_config.ConcurrencyConfig` -- now
itself a :class:`~pirn.core.concurrency.concurrency_limits.ConcurrencyLimits`
subclass -- as the per-backend knob: a shared ``default`` applies to any
backend without an explicit entry, while ``overrides`` sizes named backends
individually. Subclassing ``ConcurrencyLimits`` gives every named backend a
real ``groups`` entry (:meth:`ConcurrencyLimits.group_limit`,
:attr:`ConcurrencyLimits.groups`) alongside the pre-migration ``default``/
``overrides`` shape, so a caller migrating onto the engine can read the
equivalent limits straight off this value instead of re-deriving them.

``default`` only ever applies to a backend key discovered lazily at
:meth:`for_backend` time -- one that cannot be a fixed ``groups`` entry
ahead of time -- so ``groups`` here is a snapshot of the backends named in
``overrides``, not every backend this config could ever size.

Disclosed behaviour change: since an override's key doubles as a
``ConcurrencyLimits`` group name, it must now satisfy the knot id charset
(``ConcurrencyLimits.validate_group_name`` -- alphanumeric, underscore,
hyphen, dot, colon); a backend name with other characters, accepted before
this migration, now raises at construction.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from typing import Any

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pydantic import BaseModel

from pirn_agents.performance.concurrency_config import ConcurrencyConfig


class BulkheadConfig(ConcurrencyLimits):
    """Deprecated: how each backend's isolated concurrency pool is sized."""

    default: ConcurrencyConfig
    overrides: Mapping[str, ConcurrencyConfig]

    def __init__(
        self,
        *,
        default: ConcurrencyConfig | None = None,
        overrides: Mapping[str, ConcurrencyConfig] | None = None,
    ) -> None:
        """Build the config.

        Args:
            default: Config used for any backend not named in ``overrides``.
                Defaults to a stock :class:`ConcurrencyConfig`.
            overrides: Per-backend-key config overriding the default for
                those keys.

        Raises:
            TypeError: If ``default`` is not a :class:`ConcurrencyConfig`,
                ``overrides`` is not a mapping, or any of its values is not
                a :class:`ConcurrencyConfig`.
        """
        resolved_default = default if default is not None else ConcurrencyConfig()
        if not isinstance(resolved_default, ConcurrencyConfig):
            raise TypeError(
                f"BulkheadConfig: default must be a ConcurrencyConfig, "
                f"got {type(resolved_default).__name__}"
            )
        resolved_overrides: Mapping[str, ConcurrencyConfig] = (
            overrides if overrides is not None else {}
        )
        if not isinstance(resolved_overrides, Mapping):
            raise TypeError(
                f"BulkheadConfig: overrides must be a Mapping, "
                f"got {type(resolved_overrides).__name__}"
            )
        for key, value in resolved_overrides.items():
            if not isinstance(value, ConcurrencyConfig):
                raise TypeError(
                    f"BulkheadConfig: overrides[{key!r}] must be a ConcurrencyConfig, "
                    f"got {type(value).__name__}"
                )
        warnings.warn(
            "BulkheadConfig is deprecated (ADR agents-speaks-core WS4b/PIR-866): declare "
            "ConcurrencyLimits(groups={backend: n, ...}) on the run instead",
            DeprecationWarning,
            stacklevel=2,
        )
        frozen_overrides = dict(resolved_overrides)
        groups = {name: cfg.max_concurrency for name, cfg in frozen_overrides.items()}
        # Not ``super().__init__(...)``: pydantic's pyright plugin synthesizes
        # ``ConcurrencyLimits.__init__`` from *its own* two fields only, so a
        # call naming this subclass's ``default``/``overrides`` would not
        # type-check through it. ``BaseModel.__init__`` is the untyped-``**data``
        # constructor every pydantic model actually runs; validation still
        # goes through ``type(self)``'s full schema (all four fields).
        BaseModel.__init__(
            self, groups=groups, default=resolved_default, overrides=frozen_overrides
        )

    def for_backend(self, backend: str) -> ConcurrencyConfig:
        """Return the pool config for ``backend`` (override, else default)."""
        return self.overrides.get(backend, self.default)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Deprecated compat: the pre-migration audit projection."""
        return {
            "default": self.default._pirn_audit_dict(),
            "overrides": {key: value._pirn_audit_dict() for key, value in self.overrides.items()},
        }
