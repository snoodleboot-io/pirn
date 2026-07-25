"""Mirrored + security tests for the root-scoped filesystem tools (PIR-155).

Uses a per-test ``tmp_path`` root so nothing outside the test scope is touched.
Covers happy-path read/write/list/glob, output-size caps, and the security
guarantees: ``..`` traversal, absolute paths, symlink escapes, and non-existent
roots are all rejected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pirn_agents.tools.filesystem.glob_tool import GlobTool
from pirn_agents.tools.filesystem.list_dir_tool import ListDirTool
from pirn_agents.tools.filesystem.read_file_tool import ReadFileTool
from pirn_agents.tools.filesystem.write_file_tool import WriteFileTool
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_status import ToolStatus


class TestReadFile:
    async def test_reads_in_root_file(self, tmp_path: Path) -> None:
        (tmp_path / "hello.txt").write_text("hi there", encoding="utf-8")
        tool = ReadFileTool(root=tmp_path)
        result = await tool.invoke({"path": "hello.txt"})
        assert result["content"] == "hi there"
        assert result["truncated"] is False
        assert result["bytes"] == 8

    async def test_truncates_oversized_read(self, tmp_path: Path) -> None:
        (tmp_path / "big.txt").write_text("x" * 5000, encoding="utf-8")
        tool = ReadFileTool(root=tmp_path, max_bytes=100)
        result = await tool.invoke({"path": "big.txt"})
        assert result["truncated"] is True
        assert len(result["content"]) == 100
        assert result["bytes"] == 5000

    async def test_rejects_parent_traversal(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
        tool = ReadFileTool(root=root)
        with pytest.raises(ValueError, match="traversal"):
            await tool.invoke({"path": "../secret.txt"})

    async def test_rejects_absolute_path(self, tmp_path: Path) -> None:
        tool = ReadFileTool(root=tmp_path)
        with pytest.raises(ValueError, match="absolute"):
            await tool.invoke({"path": "/etc/passwd"})

    async def test_rejects_symlink_escape(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("leak", encoding="utf-8")
        link = root / "link.txt"
        link.symlink_to(outside)
        tool = ReadFileTool(root=root)
        with pytest.raises(ValueError, match="symlink"):
            await tool.invoke({"path": "link.txt"})

    async def test_rejects_symlinked_directory_component(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        (outside_dir / "f.txt").write_text("leak", encoding="utf-8")
        (root / "d").symlink_to(outside_dir, target_is_directory=True)
        tool = ReadFileTool(root=root)
        with pytest.raises(ValueError, match="symlink"):
            await tool.invoke({"path": "d/f.txt"})

    def test_nonexistent_root_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="root does not exist"):
            ReadFileTool(root=tmp_path / "missing")

    async def test_missing_file_is_error_result(self, tmp_path: Path) -> None:
        tool = ReadFileTool(root=tmp_path)
        call = ToolCall(tool_name="read_file", arguments={"path": "nope.txt"}, call_id="c")
        outcome = await tool.as_tool_result(call)
        assert outcome.status is ToolStatus.ERROR
        assert outcome.error is not None


class TestWriteFile:
    async def test_writes_in_root(self, tmp_path: Path) -> None:
        tool = WriteFileTool(root=tmp_path)
        result = await tool.invoke({"path": "out.txt", "content": "data"})
        assert result["bytes_written"] == 4
        assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "data"

    async def test_rejects_oversized_content(self, tmp_path: Path) -> None:
        tool = WriteFileTool(root=tmp_path, max_bytes=10)
        with pytest.raises(ValueError, match="exceeds max_bytes"):
            await tool.invoke({"path": "out.txt", "content": "x" * 50})

    async def test_rejects_traversal(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        tool = WriteFileTool(root=root)
        with pytest.raises(ValueError, match="traversal"):
            await tool.invoke({"path": "../escape.txt", "content": "x"})

    async def test_rejects_missing_parent(self, tmp_path: Path) -> None:
        tool = WriteFileTool(root=tmp_path)
        with pytest.raises(ValueError, match="parent directory"):
            await tool.invoke({"path": "no/such/dir/out.txt", "content": "x"})


class TestListDir:
    async def test_lists_entries(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "sub").mkdir()
        tool = ListDirTool(root=tmp_path)
        result = await tool.invoke({})
        names = {e["name"]: e["type"] for e in result["entries"]}
        assert names == {"a.txt": "file", "sub": "dir"}
        assert result["truncated"] is False

    async def test_caps_entry_count(self, tmp_path: Path) -> None:
        for i in range(20):
            (tmp_path / f"f{i}.txt").write_text("x", encoding="utf-8")
        tool = ListDirTool(root=tmp_path, max_entries=5)
        result = await tool.invoke({"path": ""})
        assert len(result["entries"]) == 5
        assert result["count"] == 20
        assert result["truncated"] is True

    async def test_rejects_traversal(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        tool = ListDirTool(root=root)
        with pytest.raises(ValueError, match="traversal"):
            await tool.invoke({"path": ".."})


class TestGlob:
    async def test_matches_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x", encoding="utf-8")
        (tmp_path / "b.txt").write_text("x", encoding="utf-8")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.py").write_text("x", encoding="utf-8")
        tool = GlobTool(root=tmp_path)
        result = await tool.invoke({"pattern": "**/*.py"})
        assert set(result["matches"]) == {"a.py", "sub/c.py"}

    async def test_caps_results(self, tmp_path: Path) -> None:
        for i in range(10):
            (tmp_path / f"f{i}.log").write_text("x", encoding="utf-8")
        tool = GlobTool(root=tmp_path, max_results=3)
        result = await tool.invoke({"pattern": "*.log"})
        assert len(result["matches"]) == 3
        assert result["count"] == 10
        assert result["truncated"] is True

    async def test_symlink_escape_excluded(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside.py"
        outside.write_text("x", encoding="utf-8")
        (root / "link.py").symlink_to(outside)
        (root / "real.py").write_text("x", encoding="utf-8")
        tool = GlobTool(root=root)
        result = await tool.invoke({"pattern": "*.py"})
        assert result["matches"] == ["real.py"]

    async def test_rejects_absolute_pattern(self, tmp_path: Path) -> None:
        tool = GlobTool(root=tmp_path)
        with pytest.raises(ValueError, match="absolute"):
            await tool.invoke({"pattern": "/etc/*"})

    async def test_rejects_traversal_pattern(self, tmp_path: Path) -> None:
        tool = GlobTool(root=tmp_path)
        with pytest.raises(ValueError, match="'\\.\\.'"):
            await tool.invoke({"pattern": "../*"})
