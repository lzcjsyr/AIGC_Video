from pathlib import Path

from core import prompts, resources
from core.infra.hyperframes import runtime


def test_library_defaults_to_the_engine_folder(monkeypatch):
    monkeypatch.delenv(resources.LIBRARY_ENV, raising=False)
    assert resources.prompts_dir() == resources.ENGINE_ROOT / "prompts"
    assert resources.skills_dir() == resources.ENGINE_ROOT / "skills"


def test_library_override_relocates_prompts_and_skills(monkeypatch, tmp_path: Path):
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "step2_summary.md").write_text("relocated", encoding="utf-8")
    monkeypatch.setenv(resources.LIBRARY_ENV, str(tmp_path))
    assert resources.skills_dir() == tmp_path.resolve() / "skills"
    assert prompts._load_prompt_file("step2_summary.md") == "relocated"


def test_hyperframes_command_prefers_the_bundled_cli(monkeypatch):
    monkeypatch.delenv(runtime.BUNDLED_CLI_ENV, raising=False)
    assert runtime.hyperframes_command() == ["npx", "--yes", runtime.HYPERFRAMES_VERSION]
    monkeypatch.setenv(runtime.BUNDLED_CLI_ENV, "/app/hyperframes/cli.js")
    assert runtime.hyperframes_command()[1:] == ["/app/hyperframes/cli.js"]
