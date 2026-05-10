"""``Optional`` — wrapper knot that converts any upstream failure to ``Skipped``.

Wrap any knot with ``Optional`` to make its failure non-fatal.  If the
wrapped knot produces ``Err`` or is itself ``Skipped``, ``Optional``
emits ``Skipped`` so downstream knots see a clean opt-out rather than a
failure.  If the wrapped knot succeeds, its value passes through unchanged.

Example::

    file_src = FileSource(store=s3, format=parquet_fmt, key="data/train.parquet",
                          _config=KnotConfig(id="file"))
    safe_src = Optional(knot=file_src, _config=KnotConfig(id="safe-file"))

    # safe_src produces Skipped if file_src fails; otherwise the DataBatch.
"""

from __future__ import annotations

from typing import Any

from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.skipped import Skipped


class Optional(Knot):
    """Wrapper knot: forwards the wrapped knot's value or converts failure to ``Skipped``."""

    def __init__(
        self,
        *,
        knot: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(knot, Knot):
            raise TypeError("Optional: 'knot' must be a Knot instance")
        config = KnotConfig(
            id=_config.id,
            error_policy=ErrorPolicy.RECEIVE_ERRORS,
            validate_io=False,
            description=_config.description,
            tags=_config.tags,
            transport=_config.transport,
        )
        super().__init__(wrapped=knot, _config=config, **kwargs)

    async def __call__(self, parent_results: Any) -> Any:
        from pirn.core.ok import Ok

        result = await super().__call__(parent_results)
        if isinstance(result, Ok) and isinstance(result.value, Skipped):
            return result.value
        return result

    async def process(self, wrapped: Any, **_: Any) -> Any:
        """Pass the wrapped knot's value through, or return Skipped if it failed.

        Args:
            wrapped: Raw ``Ok | Err | Skipped`` result from the wrapped knot,
                received via ``RECEIVE_ERRORS`` policy.

        Returns:
            The unwrapped value when the wrapped knot succeeded, or
            ``Skipped`` when it produced ``Err`` or ``Skipped``.
        """
        from pirn.core.err import Err
        from pirn.core.ok import Ok

        if isinstance(wrapped, Ok):
            return wrapped.value
        if isinstance(wrapped, (Err, Skipped)):
            return Skipped(reason="optional")
        return wrapped
