from pathlib import Path

from core.pipeline import scanner
from core.pipeline.scanner import scan_input_files as scan_pipeline_input_files


def test_relative_input_path_is_anchored_to_project_root(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "project"
    input_dir = project_root / "input"
    input_dir.mkdir(parents=True)
    (input_dir / "notes.txt").write_text("content", encoding="utf-8")

    monkeypatch.setattr(scanner, "__file__", str(project_root / "core" / "pipeline" / "scanner.py"))
    monkeypatch.chdir(tmp_path)

    assert [item["name"] for item in scanner.scan_input_files()] == ["notes.txt"]


def test_input_scanners_include_agent_readable_text_and_office_formats(tmp_path: Path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "source_folder").mkdir()
    for name in [
        "book.pdf",
        "book.epub",
        "book.mobi",
        "book.azw3",
        "notes.md",
        "draft.txt",
        "outline.docx",
        "legacy.doc",
        "cover.png",
    ]:
        (input_dir / name).write_text("x", encoding="utf-8")

    expected = {
        ".pdf",
        ".epub",
        ".mobi",
        ".azw3",
        ".md",
        ".txt",
        ".docx",
        ".doc",
    }

    discovered = scan_pipeline_input_files(str(input_dir))
    extensions = {item["extension"] for item in discovered}
    directories = {item["name"] for item in discovered if item.get("is_directory")}

    assert expected <= extensions
    assert ".png" not in extensions
    assert "source_folder" in directories
