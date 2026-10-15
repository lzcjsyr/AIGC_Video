from pathlib import Path

from core.pipeline.scanner import scan_output_projects as scan_core_output_projects


def _make_project(output_dir: Path, name: str) -> None:
    (output_dir / name / "text").mkdir(parents=True)


def test_output_projects_sort_by_folder_numeric_prefix(tmp_path: Path) -> None:
    for name in [
        "160.中国历代政治得失_xiaomi",
        "template_project",
        "10.交易的艺术",
        "159.",
        "2.非理性繁荣与金融危机",
    ]:
        _make_project(tmp_path, name)

    expected = [
        "2.非理性繁荣与金融危机",
        "10.交易的艺术",
        "159.",
        "160.中国历代政治得失_xiaomi",
        "template_project",
    ]

    assert [p["name"] for p in scan_core_output_projects(str(tmp_path))] == expected
