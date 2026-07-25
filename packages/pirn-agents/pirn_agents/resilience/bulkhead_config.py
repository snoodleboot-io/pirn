"""``BulkheadConfig`` — per-backend concurrency pool sizing with a default."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.performance.concurrency_config import ConcurrencyConfig


@dataclass(frozen=True)
class BulkheadConfig(PirnOpaqueValue):
    """How each backend's isolated concurrency pool is sized.

    Reuses the F10 :class:`~pirn_agents.performance.concurrency_config.ConcurrencyConfig`
    as the per-pool knob: a shared ``default`` applies to any backend without an
    explicit entry, while ``overrides`` sizes named backends individually. A
    frozen value, so the whole bulkhead posture lives in one object rather than
    scattered semaphore literals.

    Attributes
    ----------
    default:
        Config used for any backend not named in ``overrides``. Defaults to the
        stock :class:`ConcurrencyConfig` posture.
    overrides:
        Per-backend-key config overriding the default for those keys.
    """

    default: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    overrides: Mapping[str, ConcurrencyConfig] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the default and every override is a ``ConcurrencyConfig``."""
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

    def for_backend(self, backend: str) -> ConcurrencyConfig:
        """Return the pool config for ``backend`` (override, else default)."""
        return self.overrides.get(backend, self.default)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "default": self.default._pirn_audit_dict(),
            "overrides": {key: value._pirn_audit_dict() for key, value in self.overrides.items()},
        }
