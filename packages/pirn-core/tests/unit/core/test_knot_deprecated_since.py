"""Tests for ``Knot._deprecated_since`` / ``Knot._deprecation_notice``.

The seam a Knot-shaped deprecation shim uses to raise a ``DeprecationWarning``
on construction without putting anything beyond a single
``super().__init__(...)`` call in its own ``__init__`` (Rule 1,
``knot-design-rules.md``). Lives in ``Knot._bootstrap`` rather than
``Knot.__init__`` because framework primitives that bypass the standard
constructor introspection (``Parameter`` among them) still call
``_bootstrap`` — see ``resolved_value_knot.py`` for a concrete shim built on
``Parameter``. ADR agents-speaks-core WS5b.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry


class _OrdinaryKnot(Knot):
    async def process(self, value: int, **_: Any) -> int:
        return value


class _UnconditionallyDeprecatedKnot(Knot):
    _deprecated_since: ClassVar[str | None] = "test-marker"

    async def process(self, value: int, **_: Any) -> int:
        return value


class _ConditionallyDeprecatedKnot(Knot):
    """Warns only when ``value`` was passed as a config value, not a parent."""

    _deprecated_since: ClassVar[str | None] = "test-marker"

    async def process(self, value: int, **_: Any) -> int:
        return value

    def _deprecation_notice(
        self, parents: Mapping[str, Knot], config_values: Mapping[str, Any]
    ) -> str | None:
        if "value" in parents:
            return None
        return type(self)._deprecated_since


class _DeprecatedParameterShim(Parameter):
    """Mirrors ``ResolvedValueKnot``: a ``Parameter`` subclass that bypasses
    ``Knot.__init__`` entirely, to prove the seam lives where both
    construction paths converge."""

    _deprecated_since: ClassVar[str | None] = "test-marker"

    def __init__(self, *, value: Any, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(
            f"shim:{_config.id}",
            Any,
            default=value,
            _config=_config,
            tapestry=kwargs.get("tapestry"),
        )


class TestOrdinaryKnotDoesNotWarn:
    def test_no_warning_by_default(self) -> None:
        with Tapestry(), warnings.catch_warnings():
            warnings.simplefilter("error")
            _OrdinaryKnot(value=1, _config=KnotConfig(id="k"))


class TestUnconditionalDeprecation:
    def test_warns_on_construction(self) -> None:
        with Tapestry(), warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _UnconditionallyDeprecatedKnot(value=1, _config=KnotConfig(id="k"))
        assert len(caught) == 1
        assert issubclass(caught[0].category, DeprecationWarning)
        assert "_UnconditionallyDeprecatedKnot" in str(caught[0].message)
        assert "test-marker" in str(caught[0].message)

    def test_warns_every_construction_not_just_first(self) -> None:
        with Tapestry(), warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _UnconditionallyDeprecatedKnot(value=1, _config=KnotConfig(id="k1"))
            _UnconditionallyDeprecatedKnot(value=2, _config=KnotConfig(id="k2"))
        assert len(caught) == 2

    def test_run_scoped_copy_does_not_rewarn(self) -> None:
        with Tapestry():
            knot = _UnconditionallyDeprecatedKnot(value=1, _config=KnotConfig(id="k"))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            knot.run_scoped_copy()
        assert len(caught) == 0


class TestConditionalDeprecation:
    def test_warns_for_config_value_shape(self) -> None:
        with Tapestry(), warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _ConditionallyDeprecatedKnot(value=1, _config=KnotConfig(id="k"))
        assert len(caught) == 1

    def test_silent_for_upstream_knot_shape(self) -> None:
        with Tapestry():
            upstream = _OrdinaryKnot(value=1, _config=KnotConfig(id="upstream"))
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                _ConditionallyDeprecatedKnot(value=upstream, _config=KnotConfig(id="k"))
        assert len(caught) == 0


class TestDeprecationSeamAppliesToParameterSubclasses:
    """The seam must fire for shims built on ``Parameter``, which bypasses
    ``Knot.__init__`` entirely and calls ``_bootstrap`` directly."""

    def test_warns_on_construction(self) -> None:
        with Tapestry(), warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _DeprecatedParameterShim(value="x", _config=KnotConfig(id="k"))
        assert len(caught) == 1
        assert issubclass(caught[0].category, DeprecationWarning)

    def test_ordinary_parameter_does_not_warn(self) -> None:
        with Tapestry(), warnings.catch_warnings():
            warnings.simplefilter("error")
            Parameter("p", int, default=1, _config=KnotConfig(id="p"))
