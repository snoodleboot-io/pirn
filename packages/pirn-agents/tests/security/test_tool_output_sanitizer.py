"""Tests for S3 tool-output sanitization + quarantine (PIR-260 / PIR-300, PIR-303, PIR-310).

Covers malformed (control-sequence) output, oversized payloads, and active
content (scripts, URLs, ``javascript:`` / ``data:`` URIs, event handlers). The
raw output is produced by a :class:`StubTool` double so the sanitizer is
exercised on a realistic tool-result path with no backend.
"""

from __future__ import annotations

import pytest

from pirn_agents.security.active_content_quarantine import ActiveContentQuarantine
from pirn_agents.security.sanitized_output import SanitizedOutput
from pirn_agents.security.tool_output_sanitizer import ToolOutputSanitizer
from pirn_agents.testing.stub_tool import StubTool


async def _tool_output(result: str) -> str:
    tool = StubTool(result=result)
    return str(await tool.invoke({"input": "x"}))


async def test_strips_ansi_and_control_sequences() -> None:
    # Arrange — a tool result laced with an ANSI colour escape and a NUL byte.
    raw = await _tool_output("hello \x1b[31mred\x1b[0m\x00 world\x07")

    # Act
    out = ToolOutputSanitizer().sanitize(raw)

    # Assert
    assert isinstance(out, SanitizedOutput)
    assert "\x1b" not in out.text
    assert "\x00" not in out.text
    assert "hello red world" in out.text
    assert out.stripped > 0


def test_preserves_tab_and_newline() -> None:
    out = ToolOutputSanitizer().sanitize("line1\n\tindented")
    assert out.text == "line1\n\tindented"
    assert out.stripped == 0


def test_oversized_payload_is_capped() -> None:
    sanitizer = ToolOutputSanitizer(max_chars=50)
    out = sanitizer.sanitize("A" * 500)
    assert out.truncated
    assert len(out.text) == 50
    assert out.original_length == 500


def test_small_payload_not_truncated() -> None:
    out = ToolOutputSanitizer(max_chars=50).sanitize("short")
    assert not out.truncated
    assert out.text == "short"


async def test_script_is_quarantined() -> None:
    raw = await _tool_output("intro <script>steal()</script> outro")
    out = ToolOutputSanitizer().sanitize(raw)
    assert out.has_active_content
    assert "<script" not in out.text
    assert any(item.kind == "script" for item in out.quarantined)
    assert "[QUARANTINED:script#0]" in out.text


async def test_url_is_quarantined_not_followed() -> None:
    raw = await _tool_output("see https://evil.example/leak?token=abc for details")
    out = ToolOutputSanitizer().sanitize(raw)
    assert "https://evil.example" not in out.text
    urls = [item for item in out.quarantined if item.kind == "url"]
    # Exact-match the quarantined URL (a prefix/substring check would be an
    # incomplete-URL-sanitization anti-pattern, flagged by CodeQL, and is
    # bypassable — e.g. https://evil.example.attacker.com).
    assert urls and urls[0].value == "https://evil.example/leak?token=abc"


def test_javascript_and_data_uris_quarantined() -> None:
    out = ToolOutputSanitizer().sanitize(
        "click javascript:alert(1) or load data:text/html;base64,PHN2Zz4="
    )
    kinds = {item.kind for item in out.quarantined}
    assert "javascript_uri" in kinds
    assert "data_uri" in kinds
    assert "javascript:" not in out.text
    assert "data:text/html" not in out.text


def test_event_handler_quarantined() -> None:
    out = ToolOutputSanitizer().sanitize('<div onclick="steal()">x</div>')
    assert any(item.kind == "event_handler" for item in out.quarantined)
    assert "onclick=" not in out.text


def test_clean_output_has_no_quarantine() -> None:
    out = ToolOutputSanitizer().sanitize("Just a normal factual sentence.")
    assert not out.has_active_content
    assert out.text == "Just a normal factual sentence."


def test_sanitize_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        ToolOutputSanitizer().sanitize(123)  # type: ignore[arg-type]


def test_zero_max_chars_rejected() -> None:
    with pytest.raises(ValueError):
        ToolOutputSanitizer(max_chars=0)


def test_scan_only_does_not_mutate_text() -> None:
    quarantine = ActiveContentQuarantine()
    items = quarantine.scan("visit https://a.example now")
    assert len(items) == 1
    assert items[0].kind == "url"
