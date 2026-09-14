"""``Knot._required_engines`` — run-time engines checked at construction (PIR-873)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.required_engine import RequiredEngine


class _NeedsMissingEngine(Knot):
    _required_engines: ClassVar[Sequence[RequiredEngine]] = (
        RequiredEngine("pirn_no_such_engine_873", extra="frames", package="pirn-data"),
    )

    async def process(self, **_: Any) -> int:
        return 1


class _InheritsMissingEngine(_NeedsMissingEngine):
    pass


class _NeedsPresentEngine(Knot):
    _required_engines: ClassVar[Sequence[RequiredEngine]] = (
        RequiredEngine("json", extra="unused"),
    )

    async def process(self, **_: Any) -> int:
        return 2


class TestRequiredEngine:
    def test_validates_fields(self) -> None:
        not_a_str: Any = 1
        with pytest.raises(TypeError, match="module must be a str"):
            RequiredEngine(not_a_str, extra="x")
        with pytest.raises(ValueError, match="extra must be a non-empty str"):
            RequiredEngine("json", extra="")

    def test_require_returns_the_module(self) -> None:
        import json

        assert RequiredEngine("json", extra="unused").require() is json

    def test_missing_engine_raises_install_hint_at_construction(self) -> None:
        with pytest.raises(ImportError, match=r'pip install "pirn-data\[frames\]"'):
            _NeedsMissingEngine(_config=KnotConfig(id="needs"))

    def test_requirement_is_inherited(self) -> None:
        with pytest.raises(ImportError, match=r'pip install "pirn-data\[frames\]"'):
            _InheritsMissingEngine(_config=KnotConfig(id="child"))

    def test_missing_engine_is_not_cached_as_present(self) -> None:
        for attempt in range(2):
            with pytest.raises(ImportError):
                _NeedsMissingEngine(_config=KnotConfig(id=f"needs-{attempt}"))

    def test_present_engine_constructs(self) -> None:
        knot = _NeedsPresentEngine(_config=KnotConfig(id="present"))
        assert knot.knot_id == "present"
