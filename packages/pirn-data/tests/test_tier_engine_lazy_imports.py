"""Tier-engine knots load their engine only when constructed (PIR-872).

``import pirn_data`` imports every module (the registry fill), so no module may
import an optional engine at module scope. Each tier-engine knot instead
declares its engine in ``Knot._annotation_imports``, which ``Knot`` resolves on
first construction.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import subprocess
import sys
import tomllib
from pathlib import Path

from pirn.core.knot import Knot

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
        wrong = [
            f"{knot.__name__}: {name}"
            for knot in knots
            for name, spec in (knot.__dict__.get("_annotation_imports") or {"<none>": None}).items()
            if spec is None or spec.package != "pirn-data" or spec.extra not in extras
        ]

        # Assert
        assert len(knots) > 50
        assert wrong == []
