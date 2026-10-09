"""``ExtrasBackendDenylist`` — the optional-backend denylist derived from declared extras.

The install-isolation gate asserts that importing a pirn package and its whole
submodule tree in a *base* install pulls in none of the third-party backends that
live behind an extra. Which backends those are was hand-maintained, and the hand
list drifted ~95 distributions behind what the packages' ``[project.optional-
dependencies]`` actually declare — so a module importing one of those at module
scope passed the gate.

This derives the denylist instead: for the workspace as a whole, the *extra-only*
distributions are every distribution named in any package's
``[project.optional-dependencies]`` that no package declares as a hard
``[project] dependencies`` entry. Those are exactly the ones absent from a base
install, and therefore exactly the ones that must not reach ``sys.modules``.

Distribution names are mapped to the top-level modules they install: from the
installed distribution's own metadata when it is present, otherwise from
:data:`_import_name_overrides` for the names that do not simply normalise
(``scikit-learn`` → ``sklearn``), otherwise the normalised name itself. A name
that resolves to nothing usable raises ``ValueError`` rather than being dropped —
silently dropping is how the list shrank in the first place.
"""

from __future__ import annotations

import importlib.metadata
import keyword
import re
import tomllib
from pathlib import Path
from typing import ClassVar


class ExtrasBackendDenylist:
    """Derive the optional-backend module denylist from the packages' declared extras."""

    # Distributions whose top-level import name is not the normalised distribution
    # name. Only consulted when the distribution is NOT installed (the gate runs in
    # a clean env where, by construction, almost none of them are).
    _import_name_overrides: ClassVar[dict[str, tuple[str, ...]]] = {
        "amplitude-analytics": ("amplitude",),
        "atlassian-python-api": ("atlassian",),
        "azure-cosmos": ("azure",),
        "azure-servicebus": ("azure",),
        "azure-storage-blob": ("azure",),
        "beautifulsoup4": ("bs4",),
        "databricks-sql-connector": ("databricks",),
        "emd-signal": ("PyEMD",),
        "fhir-resources": ("fhir",),
        "gcloud-aio-storage": ("gcloud",),
        "google-analytics-data": ("google",),
        "google-cloud-bigquery": ("google",),
        "google-cloud-firestore": ("google",),
        "google-cloud-pubsub": ("google",),
        "hubspot-api-client": ("hubspot",),
        "ibis-framework": ("ibis",),
        "markdown-it-py": ("markdown_it",),
        "msgpack": ("msgpack",),
        "netcdf4": ("netCDF4",),
        "odfpy": ("odf",),
        "opencv-python": ("cv2",),
        "opencv-python-headless": ("cv2",),
        "openslide-python": ("openslide",),
        "opentelemetry-api": ("opentelemetry",),
        "opentelemetry-exporter-otlp-proto-grpc": ("opentelemetry",),
        "opentelemetry-sdk": ("opentelemetry",),
        "pillow": ("PIL",),
        "protobuf": ("google",),
        "psycopg": ("psycopg",),
        "pybids": ("bids",),
        "pygithub": ("github",),
        "pylance": ("lance",),
        "pymdown-extensions": ("pymdownx",),
        "pyshp": ("shapefile",),
        "python-arango": ("arango",),
        "python-dateutil": ("dateutil",),
        "python-docx": ("docx",),
        "python-pptx": ("pptx",),
        "python-snappy": ("snappy",),
        "pywavelets": ("pywt",),
        "pyyaml": ("yaml",),
        "scikit-learn": ("sklearn",),
        "shopifyapi": ("shopify",),
        "simpleitk": ("SimpleITK",),
        "snowflake-connector-python": ("snowflake",),
        "valkey-glide": ("glide",),
    }

    # Backends that no pyproject names directly but that arrive with one that does
    # (``boto3`` under ``aioboto3``, ``confluent_kafka`` alongside ``aiokafka``).
    # They were on the hand-written list and stay denied: a module importing one at
    # module scope is the same leak.
    _undeclared_backend_modules: ClassVar[frozenset[str]] = frozenset({"boto3", "confluent_kafka"})

    @staticmethod
    def normalize(distribution: str) -> str:
        """PEP 503 normalised distribution name (lowercase, ``-`` separated)."""
        return re.sub(r"[-_.]+", "-", distribution).lower()

    @staticmethod
    def _requirement_name(spec: str) -> str:
        """The bare distribution name of a PEP 508 requirement string."""
        return re.split(r"[<>=!~;\[\( ]", spec.strip(), maxsplit=1)[0].strip()

    @staticmethod
    def _installed_top_levels() -> dict[str, set[str]]:
        """{normalised distribution: top-level modules} for everything installed."""
        index: dict[str, set[str]] = {}
        for top_level, distributions in importlib.metadata.packages_distributions().items():
            # ``packages_distributions`` also reports stub directories such as
            # ``_duckdb-stubs`` that are not importable module names.
            if not top_level.isidentifier():
                continue
            for distribution in distributions:
                key = ExtrasBackendDenylist.normalize(distribution)
                index.setdefault(key, set()).add(top_level)
        return index

    @staticmethod
    def import_names(distribution: str, installed: dict[str, set[str]]) -> tuple[str, ...]:
        """Top-level module names *distribution* installs.

        Resolution order: the installed distribution's own metadata, then the
        explicit override table, then the normalised name when it is a usable
        module name. Anything else raises ``ValueError`` — an unresolvable
        distribution must fail the gate, not vanish from the denylist.
        """
        key = ExtrasBackendDenylist.normalize(distribution)
        from_metadata = installed.get(key)
        if from_metadata:
            return tuple(sorted(from_metadata))
        override = ExtrasBackendDenylist._import_name_overrides.get(key)
        if override is not None:
            return override
        candidate = key.replace("-", "_")
        if candidate.isidentifier() and not keyword.iskeyword(candidate):
            return (candidate,)
        raise ValueError(
            f"cannot map distribution {distribution!r} to a top-level import name — "
            "add it to ExtrasBackendDenylist._import_name_overrides; an unmapped "
            "distribution would silently shrink the install-isolation denylist"
        )

    @staticmethod
    def declared_distributions(packages_root: Path) -> tuple[set[str], set[str]]:
        """``(hard, optional)`` normalised distribution names declared by the workspace."""
        if not packages_root.is_dir():
            raise ValueError(f"{packages_root}: workspace packages directory does not exist")
        hard: set[str] = set()
        optional: set[str] = set()
        found = 0
        for pyproject in sorted(packages_root.glob("*/pyproject.toml")):
            found += 1
            project = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project", {})
            for spec in project.get("dependencies", []):
                hard.add(
                    ExtrasBackendDenylist.normalize(ExtrasBackendDenylist._requirement_name(spec))
                )
            for specs in project.get("optional-dependencies", {}).values():
                for spec in specs:
                    optional.add(
                        ExtrasBackendDenylist.normalize(
                            ExtrasBackendDenylist._requirement_name(spec)
                        )
                    )
        if not found:
            raise ValueError(
                f"{packages_root}: no packages/*/pyproject.toml found — the derived "
                "denylist would be empty and the gate would check nothing"
            )
        return hard, optional

    @staticmethod
    def extra_only_distributions(packages_root: Path) -> set[str]:
        """Distributions declared only behind an extra, so absent from a base install.

        pirn's own workspace distributions are excluded: ``pirn-core[all-domains]``
        names them, but they are the software under test, not optional backends.
        """
        hard, optional = ExtrasBackendDenylist.declared_distributions(packages_root)
        return {
            name for name in optional - hard if not (name == "pirn" or name.startswith("pirn-"))
        }

    @staticmethod
    def derive(packages_root: Path) -> frozenset[str]:
        """Top-level module names that a base install must never import."""
        installed = ExtrasBackendDenylist._installed_top_levels()
        modules: set[str] = set(ExtrasBackendDenylist._undeclared_backend_modules)
        for distribution in sorted(ExtrasBackendDenylist.extra_only_distributions(packages_root)):
            modules.update(ExtrasBackendDenylist.import_names(distribution, installed))
        return frozenset(modules)
