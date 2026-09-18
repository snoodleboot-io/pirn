"""Tier-engine knots load their engine only when constructed (PIR-872, PIR-873).

``import pirn_data`` imports every module (the registry fill), so no module may
import an optional engine at module scope. Each tier-engine knot instead
*declares* its engine, and ``Knot`` resolves the declaration on first
construction — so a missing engine raises its install hint when the pipeline is
built rather than hours into a run.

There are two declarations, and which one a knot uses is not a matter of taste
(PIR-873):

* ``Knot._annotation_imports`` binds a name that ``process()``'s **annotations**
  use — a type from the engine, imported only under ``if TYPE_CHECKING:``.
* ``Knot._required_engines`` declares an engine the knot **calls at run time**
  but whose types its annotations never name.

Every ``frames/*`` and ``lazy/*`` knot but two was previously declaring its
engine through ``_annotation_imports`` under a key (``pd``, ``pl``, ``pa``,
``duckdb``, ``dd``, ``ibis``, ``ray``, ...) that appeared nowhere in its
annotations — the mapping was being used as an install check, so Rule 10 no
longer meant what it said and a reader could not tell a real annotation binding
from a run-time requirement. This test now accepts either declaration and insists
on one of them, so the distinction is enforced rather than merely documented.
"""

from __future__ import annotations

import builtins
import importlib
import inspect
import pkgutil
import subprocess
import sys
import tomllib
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, ClassVar

import pytest
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.required_engine import RequiredEngine

import pirn_data

_ENGINE_PACKAGES = (
    "pirn_data.frames.datafusion",
    "pirn_data.frames.duckdb",
    "pirn_data.frames.pandas",
    "pirn_data.frames.polars",
    "pirn_data.frames.pyarrow",
    "pirn_data.lazy.dask",
    "pirn_data.lazy.ibis",
    "pirn_data.lazy.ray",
)
_ENGINES = ("datafusion", "duckdb", "pandas", "polars", "pyarrow", "dask", "ibis", "ray")


class TestTierEngineLazyImports:
    @staticmethod
    def _engine_knots() -> list[type[Knot]]:
        knots: list[type[Knot]] = []
        for package_name in _ENGINE_PACKAGES:
            package = importlib.import_module(package_name)
            for module_info in pkgutil.walk_packages(package.__path__, prefix=f"{package_name}."):
                module = importlib.import_module(module_info.name)
                for _, member in inspect.getmembers(module, inspect.isclass):
                    if issubclass(member, Knot) and member.__module__ == module.__name__:
                        knots.append(member)
        return knots

    @staticmethod
    def _declarations(knot: type[Knot]) -> list[tuple[str, str, str]]:
        """``(where, extra, package)`` for every engine declaration on ``knot`` itself."""
        found: list[tuple[str, str, str]] = []
        for name, spec in (knot.__dict__.get("_annotation_imports") or {}).items():
            found.append((f"_annotation_imports[{name!r}]", spec.extra, spec.package))
        for engine in knot.__dict__.get("_required_engines") or ():
            found.append((f"_required_engines[{engine.module!r}]", engine.extra, engine.package))
        return found

    def test_importing_pirn_data_loads_no_optional_engine(self) -> None:
        # Arrange
        probe = f"import sys, pirn_data; print(sorted(m for m in {_ENGINES!r} if m in sys.modules))"

        # Act
        completed = subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, text=True, check=True
        )

        # Assert
        assert completed.stdout.strip() == "[]"

    def test_every_tier_engine_knot_declares_its_engine_with_a_real_extra(self) -> None:
        # Arrange
        pyproject = Path(pirn_data.__file__).resolve().parents[1] / "pyproject.toml"
        extras = set(tomllib.loads(pyproject.read_text())["project"]["optional-dependencies"])
        knots = self._engine_knots()

        # Act
        wrong: list[str] = []
        for knot in knots:
            declarations = self._declarations(knot)
            if not declarations:
                wrong.append(f"{knot.__name__}: declares no engine")
                continue
            wrong.extend(
                f"{knot.__name__}: {where} -> {package}[{extra}]"
                for where, extra, package in declarations
                if package != "pirn-data" or extra not in extras
            )

        # Assert
        assert len(knots) > 50
        assert wrong == []

    def test_annotation_imports_only_bind_names_the_annotations_use(self) -> None:
        """Rule 10 means what it says: a key there is a name ``process()`` annotates with.

        Before PIR-873 every one of these knots kept its engine here under a key
        its annotations never mentioned, so this assertion had 66 violations.
        """
        # Arrange
        knots = self._engine_knots()

        # Act
        stray: list[str] = []
        for knot in knots:
            declared = knot.__dict__.get("_annotation_imports") or {}
            if not declared:
                continue
            signature = inspect.signature(knot.process)
            annotations = " | ".join(
                str(parameter.annotation)
                for parameter in signature.parameters.values()
                if parameter.annotation is not inspect.Parameter.empty
            )
            if signature.return_annotation is not inspect.Signature.empty:
                annotations += f" | {signature.return_annotation}"
            stray.extend(
                f"{knot.__name__}: _annotation_imports[{name!r}] names nothing in process()"
                for name in declared
                if name not in annotations.replace("[", " ").replace("]", " ").split()
                and name not in annotations
            )

        # Assert
        assert stray == []

    @pytest.mark.parametrize(
        ("module_path", "knot_name", "engine", "extra", "input_name"),
        [
            (
                "pirn_data.frames.polars.polars_filter",
                "PolarsFilter",
                "polars",
                "polars",
                "expression",
            ),
            ("pirn_data.lazy.ibis.ibis_filter", "IbisFilter", "ibis", "ibis", "predicate"),
            ("pirn_data.lazy.dask.dask_filter", "DaskFilter", "dask", "dask", "predicate"),
        ],
    )
    def test_a_missing_declared_engine_raises_the_install_hint_at_construction(
        self, module_path: str, knot_name: str, engine: str, extra: str, input_name: str
    ) -> None:
        """Construction, not the first run, is where a missing engine surfaces.

        The engine is made unimportable for the duration, then the knot is
        constructed. Without a declaration the construction succeeds and the
        failure waits until ``process()`` runs — mid-pipeline. With one it raises
        here, naming the extra that fixes it.
        """
        # Arrange
        knot_class: type[Knot] = getattr(importlib.import_module(module_path), knot_name)
        self._forget_engine_cache(knot_class)

        # Act / Assert
        try:
            with (
                _engine_unimportable(engine),
                pytest.raises(ImportError, match=rf'pip install "pirn-data\[{extra}\]"'),
            ):
                knot_class(
                    batch=_StubBatch(_config=KnotConfig(id="stub")),
                    **{input_name: lambda frame: frame},
                    _config=KnotConfig(id="probe"),
                )
        finally:
            self._forget_engine_cache(knot_class)

    def test_the_seam_reports_an_engine_that_is_simply_absent(self) -> None:
        """``_required_engines`` names a module nothing can provide -> the hint, at construction."""

        class _NeedsNothingInstallable(Knot):
            _required_engines: ClassVar[Sequence[RequiredEngine]] = (
                RequiredEngine("pirn_data_no_such_engine", extra="data", package="pirn-data"),
            )

            async def process(self, **_: Any) -> None:
                return None

        with pytest.raises(ImportError, match=r'pip install "pirn-data\[data\]"'):
            _NeedsNothingInstallable(_config=KnotConfig(id="absent"))

    @staticmethod
    def _forget_engine_cache(knot_class: type[Knot]) -> None:
        """Drop the per-class caches so the next construction re-resolves the declaration."""
        Knot._engines_present.discard(knot_class)
        Knot._annotation_namespaces.pop(knot_class, None)


class _StubBatch(Knot):
    """A parent for the construction probe; it never runs."""

    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


def _engine_unimportable(engine: str) -> Any:
    """Context manager making ``engine`` (and its submodules) fail to import."""
    import contextlib

    @contextlib.contextmanager
    def _blocked() -> Iterator[None]:
        real_import = builtins.__import__
        cached = {
            name: module
            for name, module in sys.modules.items()
            if name == engine or name.startswith(engine + ".")
        }
        for name in cached:
            del sys.modules[name]

        def _blocking_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == engine or name.startswith(engine + "."):
                raise ImportError(f"No module named {engine!r}", name=engine)
            return real_import(name, *args, **kwargs)

        builtins.__import__ = _blocking_import
        try:
            yield
        finally:
            builtins.__import__ = real_import
            sys.modules.update(cached)

    return _blocked()
