"""Tests for the documentation import / code-block gate."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_doc_imports import CheckDocImports  # noqa: E402  # scripts dir is put on sys.path first
from gatekit.doc_finding import DocFinding  # noqa: E402  # scripts dir is put on sys.path first
from gatekit.doc_import_auditor import DocImportAuditor  # noqa: E402  # scripts dir is put on sys.path first
from gatekit.markdown_file_collector import MarkdownFileCollector  # noqa: E402  # scripts dir is put on sys.path first
from gatekit.source_import_resolver import SourceImportResolver  # noqa: E402  # scripts dir is put on sys.path first


def _fake_repo(tmp_path: Path) -> Path:
    """A repo with ``pirn`` (pirn-core) and ``pirn_widgets`` (pirn-widgets) packages."""
    core = tmp_path / "packages" / "pirn-core" / "pirn"
    (core / "core").mkdir(parents=True)
    (core / "__init__.py").write_text("")
    (core / "core" / "__init__.py").write_text("")
    (core / "core" / "knot.py").write_text(
        "class Knot:\n"
        "    retries: int = 0\n\n"
        "    async def process(self) -> None: ...\n"
    )
    (core / "core" / "factory.py").write_text(
        "from pirn.core.knot import Knot\n\n"
        "class Factory(Knot):\n"
        "    @staticmethod\n"
        "    def knot(fn): ...\n\n"
        "helper = 1\n"
    )
    widgets = tmp_path / "packages" / "pirn-widgets" / "pirn_widgets"
    widgets.mkdir(parents=True)
    (widgets / "__init__.py").write_text("")
    (widgets / "gear.py").write_text("class Gear: ...\n")
    return tmp_path


def _audit(tmp_path: Path, markdown: str) -> list[DocFinding]:
    auditor = DocImportAuditor(SourceImportResolver(_fake_repo(tmp_path)))
    return auditor.audit("doc.md", markdown)


def _python_block(code: str, tag: str = "python") -> str:
    return f"Intro\n\n```{tag}\n{code}```\n"


def test_resolvable_imports_have_no_findings(tmp_path: Path) -> None:
    code = (
        "from pirn.core.factory import Factory, helper\n"
        "from pirn_widgets.gear import Gear\n"
        "import pirn.core.knot\n"
    )
    assert _audit(tmp_path, _python_block(code)) == []


def test_missing_module_is_reported_with_its_line(tmp_path: Path) -> None:
    findings = _audit(
        tmp_path, _python_block("x = 1\nfrom pirn.core.gone import Thing\n")
    )
    assert [(f.line, f.rule) for f in findings] == [(5, "doc_unresolved_import")]
    assert "pirn.core.gone" in findings[0].detail


def test_missing_name_is_reported(tmp_path: Path) -> None:
    findings = _audit(tmp_path, _python_block("from pirn.core.factory import knot\n"))
    assert [f.rule for f in findings] == ["doc_unresolved_import"]
    assert "`knot` not found in `pirn.core.factory`" in findings[0].detail


def test_plain_import_of_missing_module_is_reported(tmp_path: Path) -> None:
    findings = _audit(tmp_path, _python_block("import pirn_widgets.sprocket\n"))
    assert [f.rule for f in findings] == ["doc_unresolved_import"]


def test_unknown_pirn_root_is_reported(tmp_path: Path) -> None:
    findings = _audit(tmp_path, _python_block("from pirn_missing.x import Y\n"))
    assert [f.rule for f in findings] == ["doc_unresolved_import"]


def test_submodule_import_from_package_resolves(tmp_path: Path) -> None:
    assert (
        _audit(tmp_path, _python_block("from pirn.core import knot, factory\n")) == []
    )


def test_syntax_error_block_is_reported(tmp_path: Path) -> None:
    findings = _audit(
        tmp_path, _python_block("x = 1\nresult = run(a=1, 2)\n", tag="py")
    )
    assert [(f.line, f.rule) for f in findings] == [(5, "doc_code_block_syntax")]


def test_pycon_prompts_are_stripped(tmp_path: Path) -> None:
    code = ">>> from pirn.core.knot import Knot\n>>> Knot.retries\n0\n"
    assert _audit(tmp_path, _python_block(code, tag="pycon")) == []


def test_pycon_prompts_still_check_imports(tmp_path: Path) -> None:
    code = ">>> from pirn.core.knot import Gone\n"
    findings = _audit(tmp_path, _python_block(code, tag="pycon"))
    assert [f.rule for f in findings] == ["doc_unresolved_import"]


def test_non_python_block_is_ignored(tmp_path: Path) -> None:
    assert (
        _audit(tmp_path, _python_block("from pirn.gone import X ->\n", tag="bash"))
        == []
    )


def test_untagged_block_with_pirn_import_is_checked(tmp_path: Path) -> None:
    findings = _audit(tmp_path, _python_block("from pirn.gone import X\n", tag=""))
    assert [f.rule for f in findings] == ["doc_unresolved_import"]


def test_untagged_block_that_is_not_python_is_ignored(tmp_path: Path) -> None:
    assert _audit(tmp_path, _python_block("pirn run → pipeline.yaml\n", tag="")) == []


def test_inline_path_resolving_to_class_member_passes(tmp_path: Path) -> None:
    text = "Use `pirn.core.factory.Factory.knot` or `pirn.core.knot` or `pirn_widgets.gear.Gear`.\n"
    assert _audit(tmp_path, text) == []


def test_inline_path_follows_base_class(tmp_path: Path) -> None:
    assert _audit(tmp_path, "See `pirn.core.factory.Factory.process`.\n") == []


def test_inline_path_that_does_not_resolve_is_reported(tmp_path: Path) -> None:
    text = "Line one.\nUse `pirn.core.factory.Factory.missing` and `pirn.core.Knot`.\n"
    findings = _audit(tmp_path, text)
    assert [(f.line, f.rule) for f in findings] == [
        (2, "doc_unresolved_path"),
        (2, "doc_unresolved_path"),
    ]


def test_inline_import_statement_is_checked(tmp_path: Path) -> None:
    findings = _audit(tmp_path, "Run `from pirn.core.knot import Gone; Gone()`.\n")
    assert [f.rule for f in findings] == ["doc_unresolved_import"]


def test_inline_filename_and_spans_inside_fences_are_ignored(tmp_path: Path) -> None:
    text = "Open `pirn_explorer.html`.\n\n```text\n`pirn.nowhere`\n```\n"
    assert _audit(tmp_path, text) == []


def test_quoted_telemetry_key_is_not_a_path(tmp_path: Path) -> None:
    """A quoted string that merely looks like a dotted path (a span attribute
    key, a filter expression) is prose about a string value, not a claim that
    a Python module named ``pirn.run_id`` exists."""
    text = 'Each span carries `"pirn.run_id"` as an attribute.\n'
    assert _audit(tmp_path, text) == []


def test_unquoted_bare_path_is_still_reported(tmp_path: Path) -> None:
    """Dropping the quotes turns the same text back into a bare dotted-path
    claim, which must still resolve against real source — quoting, not mere
    resemblance to a telemetry key, is what the rule keys off."""
    findings = _audit(tmp_path, "Each span carries `pirn.run_id` as an attribute.\n")
    assert [f.rule for f in findings] == ["doc_unresolved_path"]


def test_self_taught_class_import_is_not_reported(tmp_path: Path) -> None:
    """A tutorial that defines ``class Widget`` in a worked example, then shows
    a later test snippet importing it from the file the reader is instructed
    to create, is not lying about repository contents — it is teaching the
    reader to write the file. The import must not be flagged."""
    text = (
        "Create `pirn_widgets/widget.py`:\n\n"
        "```python\n"
        "class Widget:\n"
        "    ...\n"
        "```\n\n"
        "Then in your test:\n\n"
        "```python\n"
        "from pirn_widgets.widget import Widget\n"
        "```\n"
    )
    assert _audit(tmp_path, text) == []


def test_import_of_undefined_class_is_still_reported(tmp_path: Path) -> None:
    """The self-taught exemption is narrow: a document that imports a class it
    never defines anywhere in its own text is making a bare claim about
    repository contents, and that claim must still resolve."""
    findings = _audit(
        tmp_path, _python_block("from pirn_widgets.widget import Widget\n")
    )
    assert [f.rule for f in findings] == ["doc_unresolved_import"]
    assert "pirn_widgets.widget" in findings[0].detail


def test_self_taught_pass_does_not_cover_other_missing_names(tmp_path: Path) -> None:
    """A self-taught class in the mix does not give the rest of the same
    import statement a free pass — only names the document actually defines
    are exempted."""
    text = (
        "```python\n"
        "class Widget:\n"
        "    ...\n"
        "```\n\n"
        "```python\n"
        "from pirn.core.factory import Factory, Widget as _W, knot\n"
        "```\n"
    )
    findings = _audit(tmp_path, text)
    assert [f.rule for f in findings] == ["doc_unresolved_import"]
    assert "`knot` not found in `pirn.core.factory`" in findings[0].detail


def test_changelog_is_skipped_when_walking(tmp_path: Path) -> None:
    (tmp_path / "CHANGELOG.md").write_text("x")
    (tmp_path / "guide.md").write_text("x")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "vendored.md").write_text("x")
    assert MarkdownFileCollector.collect([str(tmp_path)]) == [tmp_path / "guide.md"]


def test_main_reports_findings_and_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(_python_block("from pirn.core.knot_factory import knot\n"))
    assert CheckDocImports.main([str(doc)]) == 1
    assert f"{doc}:4: [doc_unresolved_import]" in capsys.readouterr().out


def test_main_ignores_a_stale_changelog(tmp_path: Path) -> None:
    (tmp_path / "CHANGELOG.md").write_text(_python_block("from pirn.gone import X\n"))
    (tmp_path / "ok.md").write_text("Nothing to see.\n")
    assert CheckDocImports.main([str(tmp_path)]) == 0


def test_main_nonexistent_path_exits_two(tmp_path: Path) -> None:
    assert CheckDocImports.main([str(tmp_path / "missing.md")]) == 2


def test_main_zero_markdown_files_exits_two(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("x")
    assert CheckDocImports.main([str(tmp_path)]) == 2


def test_main_no_arguments_exits_two() -> None:
    assert CheckDocImports.main([]) == 2


def test_repository_docs_are_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(repo)
    targets = [
        "AGENTIC_USE.md",
        "AGENTIC_USE_SPEC.md",
        "README.md",
        "docs",
        "examples/README.md",
        "packages",
    ]
    assert CheckDocImports.main(targets) == 0
