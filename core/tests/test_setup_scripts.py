from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_windows_install_and_test_scripts_use_shared_dependency_checker() -> None:
    install_script = (REPO_ROOT / "scripts" / "install_windows.ps1").read_text(encoding="utf-8")
    test_script = (REPO_ROOT / "scripts" / "test_windows.ps1").read_text(encoding="utf-8")

    assert "-m core.dependency_check" in install_script
    assert "-m pytest" in test_script
    assert "--require-api-keys" in test_script


def test_macos_install_and_test_scripts_use_shared_dependency_checker() -> None:
    install_script = (REPO_ROOT / "scripts" / "install_macos.sh").read_text(encoding="utf-8")
    test_script = (REPO_ROOT / "scripts" / "test_macos.sh").read_text(encoding="utf-8")

    assert "-m core.dependency_check" in install_script
    assert "-m pytest" in test_script
    assert "--require-api-keys" in test_script


def test_motion_template_is_committed() -> None:
    assert (REPO_ROOT / "core" / "infra" / "motion" / "app" / "index.html").exists()
