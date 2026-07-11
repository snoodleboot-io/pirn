"""Declaration-level tests for the pirn-agents extras matrix (F2-S1 / PIR-80).

Real clean-venv resolution is a CI concern (F2-S5). Here we assert the
``[project.optional-dependencies]`` DECLARATION in ``pyproject.toml`` is correct,
provider-neutral, and keeps the base install pirn-core-only.
"""

from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

_PYPROJECT = Path(__file__).parents[1] / "pyproject.toml"

# self-reference form: "pirn-agents[<extra>]"
_SELF_REF = re.compile(r"^pirn-agents\[(?P<extra>[a-z0-9_-]+)\]$")

# expected per-provider / per-capability extras and capability bundles
_PROVIDER_EXTRAS = {
    "openai",
    "anthropic",
    "qdrant",
    "pgvector",
    "chroma",
    "local-embed",
    "cross-encoder",
}
# observability backend extra (F10 OTel-style sink) + async SQL driver (F6 base tools)
_BACKEND_EXTRAS = {"otel", "sql"}
_BUNDLE_EXTRAS = {"llm", "vector", "web", "mcp", "all"}
_EXPECTED_EXTRAS = _PROVIDER_EXTRAS | _BACKEND_EXTRAS | _BUNDLE_EXTRAS


def _load() -> dict[str, object]:
    with _PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def _req_name(requirement: str) -> str:
    """Extract the distribution name from a requirement string.

    ``"httpx>=0.27"`` -> ``"httpx"``; ``"pirn-agents[web]"`` -> ``"pirn-agents"``.
    """
    return re.split(r"[<>=!~\[ ;]", requirement.strip(), maxsplit=1)[0].lower()


def _resolve(extras: dict[str, list[str]], name: str, _seen: set[str] | None = None) -> set[str]:
    """Flatten an extra to the set of concrete (non-self-ref) distribution names."""
    seen = _seen if _seen is not None else set()
    if name in seen:
        return set()
    seen.add(name)
    out: set[str] = set()
    for req in extras.get(name, []):
        match = _SELF_REF.match(req.strip())
        if match:
            out |= _resolve(extras, match.group("extra"), seen)
        else:
            out.add(_req_name(req))
    return out


class TestExtrasMatrix(unittest.TestCase):
    def setUp(self) -> None:
        self.data = _load()
        self.project = self.data["project"]
        assert isinstance(self.project, dict)
        self.extras: dict[str, list[str]] = self.project["optional-dependencies"]

    def test_expected_extra_keys_exact(self) -> None:
        assert set(self.extras) == _EXPECTED_EXTRAS

    def test_base_dependencies_are_pirn_core_only(self) -> None:
        deps = self.project["dependencies"]
        assert isinstance(deps, list)
        names = {_req_name(d) for d in deps}
        assert names == {"pirn-core"}, f"base install leaked backends: {names}"

    def test_web_includes_httpx(self) -> None:
        assert "httpx" in _resolve(self.extras, "web")

    def test_mcp_includes_mcp(self) -> None:
        assert "mcp" in _resolve(self.extras, "mcp")

    def test_otel_extra_provides_opentelemetry(self) -> None:
        assert _resolve(self.extras, "otel") == {"opentelemetry-api"}

    def test_sql_extra_provides_aiosqlite(self) -> None:
        assert _resolve(self.extras, "sql") == {"aiosqlite"}

    def test_all_transitively_covers_every_extra(self) -> None:
        all_concrete = _resolve(self.extras, "all")
        for extra in _EXPECTED_EXTRAS - {"all"}:
            assert _resolve(self.extras, extra) <= all_concrete, (
                f"'all' does not cover extra {extra!r}"
            )

    def test_provider_neutrality_guard(self) -> None:
        # no single provider may be privileged: illustrative peers appear as equals
        assert "openai" in self.extras
        assert "anthropic" in self.extras
        assert _resolve(self.extras, "llm") == {"openai", "anthropic"}

    def test_vector_bundle_covers_every_store_as_equal_siblings(self) -> None:
        # qdrant / pgvector / chroma are equal siblings under the vector bundle
        vector = _resolve(self.extras, "vector")
        assert _resolve(self.extras, "qdrant") <= vector
        assert _resolve(self.extras, "pgvector") <= vector
        assert _resolve(self.extras, "chroma") <= vector

    def test_local_embed_and_cross_encoder_resolve_to_sentence_transformers(self) -> None:
        assert _resolve(self.extras, "local-embed") == {"sentence-transformers"}
        assert _resolve(self.extras, "cross-encoder") == {"sentence-transformers"}

    def test_pgvector_uses_async_driver(self) -> None:
        assert "asyncpg" in _resolve(self.extras, "pgvector")


if __name__ == "__main__":
    unittest.main()
