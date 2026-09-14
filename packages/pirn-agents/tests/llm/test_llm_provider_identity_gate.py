"""Gate: every content-identified LLM provider accounts for every constructor input.

An HTTP provider opts in to content identity by re-declaring
:meth:`BaseLLMProvider.content_identity` (PIR-840 PR-3). The opt-in is not
type-enforced, so a provider that gains an ``organization`` or ``extra_headers``
argument tomorrow would hash two differently-behaving instances equal, and replay
would serve one's recording to the other. That false match is the dangerous
direction this gate exists for.

Three checks:

* **Per-argument outcome.** For each content-identified provider, build a baseline,
  confirm it is content-identified and hashes equal when rebuilt (otherwise "the
  hash changed" would be vacuous), then vary each ``__init__`` parameter one at a
  time. Each parameter has a declared outcome: the hash **changes**, the provider
  **falls back** to identity, or (for the credential only, with the reason written
  down) the hash stays **equal**. The parameters covered must equal the introspected
  signature, so a new constructor argument fails here until someone decides.
* **Coverage ratchet.** Every class in the workspace (``packages/``, ``examples/``,
  ``scripts/``) that descends from ``BaseLLMProvider`` and defines
  ``content_identity`` must have a case below or a named exemption, by exact
  equality. The scan is whole-workspace and by AST, because a package-local
  registry previously missed classes defined elsewhere.
* **Inheritance ratchet.** The opt-in is not inherited, following the rule tools
  use: a subclass that does not re-declare ``content_identity`` is identity-keyed.
  Every such subclass in the workspace must be listed as intentionally
  identity-keyed, so a subclass whose author expected to inherit replay is surfaced.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import unittest
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pirn.core.content_hasher import ContentHasher
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.security.credential_ref import CredentialRef

from pirn_agents.llm.anthropic_messages_provider import AnthropicMessagesProvider
from pirn_agents.llm.base_llm_provider import BaseLLMProvider
from pirn_agents.llm.model_pricing import ModelPricing
from pirn_agents.llm.openai_compatible_provider import OpenAICompatibleProvider
from pirn_agents.llm.retry_policy import RetryPolicy

ROOT = "packages/pirn-agents/pirn_agents/llm/base_llm_provider.py::BaseLLMProvider"

#: Classes that define ``content_identity`` without being a concrete opt-in.
#: The test doubles exist to exercise the re-declaration rule itself.
#:
#: ``LLMProviderIdentityMixin`` (the actual AST-level home of
#: ``content_identity`` since the PIR-856 SRP split) does not need an entry
#: here: the workspace scan only walks *downward* from ``BaseLLMProvider``
#: (subclasses), and the mixin is one of its bases, not a subclass, so the
#: scan never visits it.
EXEMPT = frozenset(
    {
        "packages/pirn-agents/tests/llm/test_llm_provider_content_identity.py"
        "::_RedeclaredOpenAICompatibleProvider",
        "packages/pirn-agents/tests/llm/test_llm_provider_content_identity.py::Local",
    }
)

#: Subclasses that do not re-declare ``content_identity`` and are therefore
#: identity-keyed on purpose, with the reason.
INHERITS_WITHOUT_REDECLARING = {
    ROOT: (
        "content_identity lives on LLMProviderIdentityMixin (PIR-856 SRP split); "
        "BaseLLMProvider computes the shared config and cannot be instantiated directly"
    ),
    "packages/pirn-agents/pirn_agents/llm/http_structured_output_provider.py"
    "::HttpStructuredOutputProvider": "abstract base; its hooks raise NotImplementedError",
    "packages/pirn-agents/tests/llm/test_base_llm_provider.py::StubLLMProvider": "test double",
    "packages/pirn-agents/tests/llm/test_http_structured_output_provider.py"
    "::_StubStructuredProvider": "test double",
    "packages/pirn-agents/tests/llm/test_llm_provider_content_identity.py"
    "::_UndeclaredOpenAICompatibleProvider": "reproduces an inherited opt-in",
}

#: Directory names never scanned: virtualenvs, caches, and git worktrees.
SKIPPED_DIRECTORIES = frozenset(
    {".venv", "venv", "__pycache__", "node_modules", ".git", "build", "dist", ".claude"}
)

CHANGES = "changes"
FALLS_BACK = "falls back"
EQUAL = "equal"


@dataclass(frozen=True)
class Variant:
    """A replacement value for one constructor parameter and its declared outcome."""

    value: Any
    outcome: str
    reason: str = ""


async def gate_sleeper(delay: float) -> None:
    """A sleeper that is not :func:`asyncio.sleep`."""
    await asyncio.sleep(0)


def gate_rng() -> float:
    """A fixed jitter source."""
    return 0.5


def baseline_kwargs() -> dict[str, Any]:
    """Return a fully specified baseline configuration for any HTTP provider."""
    return {
        "model": "model-a",
        "base_url": "https://llm.example/v1",
        "credential": CredentialRef(secret="sk-GATE-BASELINE"),
        "retry_policy": RetryPolicy(),
        "pricing": ModelPricing(input_per_million=1.0, output_per_million=2.0),
        "timeout": 30.0,
        "default_max_tokens": 256,
        "enable_prompt_cache": False,
        "client": None,
        "sleeper": None,
        "rng": None,
    }


def http_provider_variants() -> dict[str, Variant]:
    """Return the declared outcome of varying each ``BaseLLMProvider`` parameter."""
    sleeper: Callable[[float], Awaitable[None]] = gate_sleeper
    return {
        "model": Variant("model-b", CHANGES),
        "base_url": Variant("https://other.example/v1", CHANGES),
        "credential": Variant(
            CredentialRef(secret="sk-GATE-OTHER"),
            EQUAL,
            "a secret is never identity: same model and endpoint with another key replay",
        ),
        "retry_policy": Variant(RetryPolicy(max_retries=0), CHANGES),
        "pricing": Variant(ModelPricing(input_per_million=9.0, output_per_million=2.0), CHANGES),
        "timeout": Variant(5.0, CHANGES),
        "default_max_tokens": Variant(512, CHANGES),
        "enable_prompt_cache": Variant(True, CHANGES),
        "client": Variant(object(), FALLS_BACK),
        "sleeper": Variant(sleeper, FALLS_BACK),
        "rng": Variant(gate_rng, FALLS_BACK),
    }


class TestContentIdentifiedProvidersAccountForEveryConstructorArgument(unittest.TestCase):
    def cases(self) -> dict[type[BaseLLMProvider], dict[str, Variant]]:
        """Return ``{provider type: variant per constructor parameter}``."""
        return {
            OpenAICompatibleProvider: http_provider_variants(),
            AnthropicMessagesProvider: http_provider_variants(),
        }

    def test_each_case_covers_exactly_the_constructor_signature(self) -> None:
        for provider_type, variants in self.cases().items():
            with self.subTest(provider=provider_type.__name__):
                parameters = set(inspect.signature(provider_type.__init__).parameters) - {"self"}

                assert set(variants) == parameters

    def test_only_the_credential_may_leave_the_hash_unchanged(self) -> None:
        for provider_type, variants in self.cases().items():
            with self.subTest(provider=provider_type.__name__):
                equal = {name for name, variant in variants.items() if variant.outcome == EQUAL}

                assert equal <= {"credential"}
                assert all(variants[name].reason for name in equal)

    def test_each_baseline_is_content_identified_and_stable(self) -> None:
        for provider_type in self.cases():
            with self.subTest(provider=provider_type.__name__):
                first = provider_type(**baseline_kwargs())
                second = provider_type(**baseline_kwargs())

                assert first.content_identity() is not None
                assert isinstance(first.__pirn_canonical__(), dict)
                assert ContentHasher.hash(first) == ContentHasher.hash(second)

    def test_varying_each_constructor_argument_has_its_declared_outcome(self) -> None:
        for provider_type, variants in self.cases().items():
            reference = ContentHasher.hash(provider_type(**baseline_kwargs()))
            for parameter, variant in variants.items():
                with self.subTest(provider=provider_type.__name__, parameter=parameter):
                    kwargs = {**baseline_kwargs(), parameter: variant.value}
                    varied = provider_type(**kwargs)
                    twin = provider_type(**kwargs)

                    if variant.outcome == CHANGES:
                        assert varied.content_identity() is not None
                        assert ContentHasher.hash(varied) != reference
                    elif variant.outcome == FALLS_BACK:
                        assert varied.content_identity() is None
                        assert varied.__pirn_canonical__() == PirnOpaqueValue._pirn_audit_dict(
                            varied
                        )
                        assert ContentHasher.hash(varied) != ContentHasher.hash(twin)
                    else:
                        assert variant.outcome == EQUAL
                        assert ContentHasher.hash(varied) == reference

    def test_every_content_identified_provider_in_the_workspace_has_a_case(self) -> None:
        declaring, _ = self._scan(self._workspace_root())
        covered = {
            finding
            for finding in declaring
            if any(self._is_case_for(finding, provider_type) for provider_type in self.cases())
        }

        assert declaring == covered | EXEMPT, (
            "a provider declares content_identity without a gate case (or an exemption "
            f"names a class that no longer declares it): {sorted(declaring ^ (covered | EXEMPT))}"
        )
        assert len(covered) == len(self.cases()), (
            "a gate case names a class the workspace scan no longer finds declaring it"
        )

    def test_every_subclass_that_does_not_redeclare_is_intentionally_identity_keyed(
        self,
    ) -> None:
        _, inheriting = self._scan(self._workspace_root())

        assert inheriting == set(INHERITS_WITHOUT_REDECLARING), (
            "a BaseLLMProvider subclass does not re-declare content_identity, so it is "
            "identity-keyed; re-declare it with the subclass's full config, or list it here: "
            f"{sorted(inheriting ^ set(INHERITS_WITHOUT_REDECLARING))}"
        )

    def test_every_loaded_content_identified_provider_has_a_case(self) -> None:
        """Runtime twin of the AST scan: catches opt-ins reached by dynamic bases."""
        uncovered = [
            f"{provider_type.__module__}.{provider_type.__qualname__}"
            for provider_type in self._all_subclasses(BaseLLMProvider)
            if "content_identity" in vars(provider_type)
            and provider_type not in self.cases()
            and provider_type is not BaseLLMProvider
            and not any(self._is_case_for(entry, provider_type) for entry in EXEMPT)
        ]

        assert uncovered == []

    @staticmethod
    def _is_case_for(finding: str, provider_type: type) -> bool:
        path, name = finding.rsplit("::", 1)
        module_path = provider_type.__module__.replace(".", "/") + ".py"
        return name == provider_type.__name__ and path.endswith(module_path)

    @staticmethod
    def _all_subclasses(root: type) -> set[type]:
        found: set[type] = set()
        pending = [root]
        while pending:
            for subclass in pending.pop().__subclasses__():
                if subclass not in found:
                    found.add(subclass)
                    pending.append(subclass)
        return found

    @staticmethod
    def _workspace_root() -> Path:
        for candidate in Path(__file__).resolve().parents:
            if (candidate / "packages").is_dir() and (candidate / "examples").is_dir():
                return candidate
        raise AssertionError(
            "workspace root (a directory holding packages/ and examples/) not found above "
            f"{__file__}; the coverage scan must see the whole workspace"
        )

    @staticmethod
    def _scan(workspace: Path) -> tuple[set[str], set[str]]:
        """Return ``(declaring, inheriting without re-declaring)`` descendants of the root.

        Both sets hold ``path::name`` entries for classes descending from
        ``BaseLLMProvider``; the root itself counts as declaring. A base name is
        resolved to a class defined in the same file when there is one (so an
        unrelated same-named class elsewhere does not pull a file in); otherwise it
        matches any descendant of that name, which over-reports on a collision, the
        safe direction for a gate.
        """
        classes: dict[str, list[ast.ClassDef]] = {}
        for top in ("packages", "examples", "scripts"):
            for source in sorted((workspace / top).rglob("*.py")):
                relative = source.relative_to(workspace)
                if SKIPPED_DIRECTORIES.intersection(relative.parts):
                    continue
                text = source.read_text(encoding="utf-8")
                if "Provider" not in text:
                    continue
                classes[relative.as_posix()] = [
                    node for node in ast.walk(ast.parse(text)) if isinstance(node, ast.ClassDef)
                ]
        gate = TestContentIdentifiedProvidersAccountForEveryConstructorArgument
        descendants: set[str] = {ROOT}
        while True:
            found = set(descendants)
            for path, nodes in classes.items():
                local = {node.name for node in nodes}
                for node in nodes:
                    if gate._extends_a_descendant(path, node, local, descendants):
                        found.add(f"{path}::{node.name}")
            if found == descendants:
                break
            descendants = found
        declaring = {
            f"{path}::{node.name}"
            for path, nodes in classes.items()
            for node in nodes
            if f"{path}::{node.name}" in descendants and gate._defines_content_identity(node)
        }
        return declaring, descendants - declaring

    @staticmethod
    def _extends_a_descendant(
        path: str, node: ast.ClassDef, local: set[str], descendants: set[str]
    ) -> bool:
        """Return whether any base of ``node`` resolves to a known descendant."""
        descendant_names = {entry.rsplit("::", 1)[1] for entry in descendants}
        for base in TestContentIdentifiedProvidersAccountForEveryConstructorArgument._base_names(
            node
        ):
            if base in local:
                if f"{path}::{base}" in descendants:
                    return True
            elif base in descendant_names:
                return True
        return False

    @staticmethod
    def _defines_content_identity(node: ast.ClassDef) -> bool:
        return any(
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == "content_identity"
            for item in node.body
        )

    @staticmethod
    def _base_names(node: ast.ClassDef) -> set[str]:
        return {
            base.id if isinstance(base, ast.Name) else base.attr
            for base in node.bases
            if isinstance(base, (ast.Name, ast.Attribute))
        }
