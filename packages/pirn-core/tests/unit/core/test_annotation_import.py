"""Knot annotations naming TYPE_CHECKING-only types resolve through ``_annotation_imports`` (PIR-872)."""

from __future__ import annotations

import asyncio
import importlib
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from pirn.core.annotation_import import AnnotationImport
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

_ENGINE = '''
from typing import Any

from pydantic_core import core_schema


class Frame:
    """A stand-in for an optional engine's frame type."""

    def __init__(self, rows: int) -> None:
        self.rows = rows

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> Any:
        return core_schema.is_instance_schema(cls)
'''

_LAZY_KNOT = """
from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar
from collections.abc import Mapping

from pirn.core.annotation_import import AnnotationImport
from pirn.core.knot import Knot

if TYPE_CHECKING:
    import {engine} as eng
    from {engine} import Frame


class LazyRows(Knot):
    _annotation_imports: ClassVar[Mapping[str, AnnotationImport]] = {{
        "eng": AnnotationImport("{engine}", extra="frames", package="pirn-core"),
        "Frame": AnnotationImport("{engine}", extra="frames", package="pirn-core", attribute="Frame"),
    }}

    async def process(self, frame: Frame, **_: Any) -> eng.Frame:
        return frame


class LazyRowsChild(LazyRows):
    pass
"""

_EAGER_KNOT = """
from __future__ import annotations

from typing import Any

from {engine} import Frame

from pirn.core.knot import Knot


class EagerRows(Knot):
    async def process(self, frame: Frame, **_: Any) -> Frame:
        return frame
"""


@pytest.fixture
def modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Iterator[str]:
    """Write a fake engine plus lazy and eager knot modules; yield the engine name."""
    engine = f"pirn_fake_engine_{request.node.name.replace('[', '_').replace(']', '_')}"
    (tmp_path / f"{engine}.py").write_text(_ENGINE)
    (tmp_path / f"{engine}_lazy_knot.py").write_text(
        textwrap.dedent(_LAZY_KNOT.format(engine=engine))
    )
    (tmp_path / f"{engine}_eager_knot.py").write_text(
        textwrap.dedent(_EAGER_KNOT.format(engine=engine))
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    before = set(sys.modules)
    yield engine
    for name in set(sys.modules) - before:
        sys.modules.pop(name, None)


def _import(name: str) -> ModuleType:
    return importlib.import_module(name)


class TestAnnotationImport:
    def test_importing_the_knot_module_does_not_import_the_engine(self, modules: str) -> None:
        # Act
        _import(f"{modules}_lazy_knot")

        # Assert
        assert modules not in sys.modules

    def test_right_type_is_accepted_exactly_as_by_an_eager_knot(self, modules: str) -> None:
        # Arrange
        lazy = _import(f"{modules}_lazy_knot")
        eager = _import(f"{modules}_eager_knot")
        frame = _import(modules).Frame(3)

        # Act
        with Tapestry() as tapestry:
            lazy.LazyRows(frame=frame, _config=KnotConfig(id="lazy"))
            eager.EagerRows(frame=frame, _config=KnotConfig(id="eager"))
        result = asyncio.run(tapestry.run(RunRequest()))

        # Assert
        assert result.succeeded
        assert result.outputs["lazy"] is frame
        assert result.outputs["eager"] is frame
        assert (
            lazy.LazyRows.input_annotations()["frame"]
            is eager.EagerRows.input_annotations()["frame"]
        )

    def test_wrong_type_is_rejected_exactly_as_by_an_eager_knot(self, modules: str) -> None:
        # Arrange
        lazy = _import(f"{modules}_lazy_knot")
        eager = _import(f"{modules}_eager_knot")

        # Act / Assert
        with pytest.raises(TypeError, match="config value failed validation"):
            lazy.LazyRows(frame="not a frame", _config=KnotConfig(id="lazy"), tapestry=Tapestry())
        with pytest.raises(TypeError, match="config value failed validation"):
            eager.EagerRows(
                frame="not a frame", _config=KnotConfig(id="eager"), tapestry=Tapestry()
            )

    def test_subclass_inherits_the_annotation_imports(self, modules: str) -> None:
        # Arrange
        lazy = _import(f"{modules}_lazy_knot")

        # Act
        annotations = lazy.LazyRowsChild.input_annotations()

        # Assert
        assert annotations["frame"] is _import(modules).Frame

    def test_subclass_entry_overrides_its_base(self, modules: str) -> None:
        # Arrange
        lazy = _import(f"{modules}_lazy_knot")
        override = AnnotationImport("pirn_no_such_engine_zz", extra="other", package="pirn-core")

        class Overriding(lazy.LazyRows):
            _annotation_imports = {"Frame": override}  # noqa: RUF012

        # Act / Assert
        with pytest.raises(ImportError, match=r'pip install "pirn-core\[other\]"'):
            Overriding.input_annotations()

    def test_missing_engine_raises_the_install_hint_on_construction(self, modules: str) -> None:
        # Arrange: the knot module imports; its engine then disappears.
        lazy = _import(f"{modules}_lazy_knot")
        (Path(sys.path[0]) / f"{modules}.py").unlink()
        importlib.invalidate_caches()

        # Act / Assert
        with pytest.raises(ImportError, match=r'pip install "pirn-core\[frames\]"'):
            lazy.LazyRows(frame=object(), _config=KnotConfig(id="lazy"), tapestry=Tapestry())

    def test_resolution_is_cached_per_class(self, modules: str) -> None:
        # Arrange
        lazy = _import(f"{modules}_lazy_knot")
        first = lazy.LazyRows._annotation_namespace()

        # Act
        second = lazy.LazyRows._annotation_namespace()

        # Assert
        assert first is second
        assert first["Frame"] is _import(modules).Frame


class TestAnnotationImportValue:
    def test_resolves_a_module(self) -> None:
        assert AnnotationImport("json", extra="x").resolve() is importlib.import_module("json")

    def test_resolves_an_attribute(self) -> None:
        assert (
            AnnotationImport("json", extra="x", attribute="dumps").resolve()
            is importlib.import_module("json").dumps
        )

    @pytest.mark.parametrize("field", ["module", "extra", "package"])
    def test_non_str_field_is_a_type_error(self, field: str) -> None:
        kwargs: dict[str, object] = {
            "module": "json",
            "extra": "x",
            "package": "pirn-core",
            field: 1,
        }
        with pytest.raises(TypeError, match=field):
            AnnotationImport(**kwargs)  # type: ignore[arg-type]  # deliberately wrong type

    @pytest.mark.parametrize("field", ["module", "extra", "package", "attribute"])
    def test_empty_field_is_a_value_error(self, field: str) -> None:
        kwargs: dict[str, object] = {
            "module": "json",
            "extra": "x",
            "package": "pirn-core",
            field: "",
        }
        with pytest.raises(ValueError, match=field):
            AnnotationImport(**kwargs)  # type: ignore[arg-type]  # values are str; kwargs typed object


def test_knot_base_has_an_empty_namespace() -> None:
    assert Knot._annotation_namespace() == {}
