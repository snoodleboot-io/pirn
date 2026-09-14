"""``BulkheadConfig`` — deprecated: per-backend concurrency pool sizing with a default.

Deprecated (ADR agents-speaks-core, WS4b/PIR-866). Reuses
:class:`~pirn_agents.performance.concurrency_config.ConcurrencyConfig` as the
per-pool knob: a shared ``default`` applies to any backend without an
explicit entry, while ``overrides`` sizes named backends individually.
:meth:`to_concurrency_limits` projects ``overrides`` into the equivalent core
:class:`~pirn.core.concurrency.concurrency_limits.ConcurrencyLimits` groups
mapping -- ``default`` cannot be represented there: it applies to a backend
key discovered lazily at :meth:`for_backend` time, which is not a fixed
``groups`` entry a real run declares ahead of time.

Kept a plain frozen dataclass rather than a ``ConcurrencyLimits`` subclass
for the same reason as ``ConcurrencyConfig`` -- see that module's docstring.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.performance.concurrency_config import ConcurrencyConfig


@dataclass(frozen=True)
class BulkheadConfig(PirnOpaqueValue):
    """Deprecated: how each backend's isolated concurrency pool is sized.

    Attributes:
        default: Config used for any backend not named in ``overrides``.
            Defaults to the stock :class:`ConcurrencyConfig` posture.
        overrides: Per-backend-key config overriding the default for those
            keys.
    """

    default: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    overrides: Mapping[str, ConcurrencyConfig] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the default and every override; warn deprecated."""
        if not isinstance(self.default, ConcurrencyConfig):
            raise TypeError(
                f"BulkheadConfig: default must be a ConcurrencyConfig, "
                f"got {type(self.default).__name__}"
            )
        if not isinstance(self.overrides, Mapping):
            raise TypeError(
                f"BulkheadConfig: overrides must be a Mapping, got {type(self.overrides).__name__}"
            )
        for key, value in self.overrides.items():
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

    def for_backend(self, backend: str) -> ConcurrencyConfig:
        """Return the pool config for ``backend`` (override, else default)."""
        return self.overrides.get(backend, self.default)

    def to_concurrency_limits(self) -> ConcurrencyLimits:
        """The equivalent ``ConcurrencyLimits`` for the backends named in ``overrides``.

        Only the explicitly overridden backends are represented as groups: a
        backend covered only by ``default`` has no fixed name to declare
        ahead of time -- see the module docstring.
        """
        return ConcurrencyLimits(
            groups={name: cfg.max_concurrency for name, cfg in self.overrides.items()}
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "default": self.default._pirn_audit_dict(),
            "overrides": {key: value._pirn_audit_dict() for key, value in self.overrides.items()},
        }
