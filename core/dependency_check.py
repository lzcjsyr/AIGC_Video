"""Deployment dependency checks shared by install and test scripts."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence


MIN_PYTHON_VERSION = (3, 10)

PACKAGE_IMPORT_NAMES = {
    "pillow": "PIL",
    "python-dotenv": "dotenv",
    "python-docx": "docx",
    "pymupdf": "fitz",
    "volcengine-python-sdk": "volcenginesdkarkruntime",
    "google-genai": "google.genai",
    "json-repair": "json_repair",
    "pyyaml": "yaml",
}

PROVIDER_KEY_GROUPS = {
    "mimo": ("MIMO_API_KEY",),
    "kimi": ("KIMI_API_KEY", "MOONSHOT_API_KEY"),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "siliconflow": ("SILICONFLOW_KEY",),
    "volcengine": ("VOLCENGINE_API_KEY", "SEEDREAM_API_KEY"),
    "doubao": ("VOLCENGINE_API_KEY", "SEEDREAM_API_KEY"),
    "google": ("GOOGLE_CLOUD_API_KEY", "GOOGLE_CLOUD_PROJECT", "GOOGLE_PROJECT_ID"),
    "google_adc": ("GOOGLE_CLOUD_PROJECT", "GOOGLE_PROJECT_ID", "GOOGLE_APPLICATION_CREDENTIALS"),
    "bytedance": ("BYTEDANCE_TTS_API_KEY", "BYTEDANCE_TTS_VOICE_ID"),
}


@dataclass(frozen=True)
class CheckItem:
    name: str
    ok: bool
    detail: str
    fix: str = ""


@dataclass(frozen=True)
class DependencyReport:
    items: tuple[CheckItem, ...]

    @property
    def ok(self) -> bool:
        return all(item.ok for item in self.items)

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "items": [
                {"name": item.name, "ok": item.ok, "detail": item.detail, "fix": item.fix}
                for item in self.items
            ],
        }

    def format_text(self) -> str:
        lines = ["依赖检查结果:"]
        for item in self.items:
            status = "OK" if item.ok else "FAIL"
            lines.append(f"- [{status}] {item.name}: {item.detail}")
            if not item.ok and item.fix:
                lines.append(f"  修复: {item.fix}")
        return "\n".join(lines)


class DependencyChecker:
    def __init__(
        self,
        *,
        repo_root: Path | str | None = None,
        which: Callable[[str], str | None] = shutil.which,
        import_checker: Callable[[str], bool] | None = None,
        python_version: Sequence[int] | None = None,
    ) -> None:
        self.repo_root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
        self.which = which
        self.import_checker = import_checker or self._can_import
        self.python_version = tuple(python_version or sys.version_info[:3])

    def check(self, *, require_api_keys: bool = False) -> DependencyReport:
        items = [
            self._check_python(),
            self._check_command("FFmpeg", "ffmpeg", "安装 FFmpeg，并确保 ffmpeg 在 PATH 中。"),
            self._check_command("Node.js", "node", "安装 Node.js 22 或更新版本。"),
            self._check_command("npm", "npm", "安装 Node.js 时勾选 npm，并重开终端。"),
            self._check_motion_package_json(),
            self._check_motion_template(),
            self._check_motion_skill_bundle(),
            self._check_python_packages(),
            self._check_env_file(),
            self._check_music_dir(),
            self._check_input_dir(),
        ]
        if require_api_keys:
            items.append(self._check_api_keys())
        return DependencyReport(tuple(items))

    def _check_python(self) -> CheckItem:
        version = ".".join(str(part) for part in self.python_version[:3])
        if self.python_version >= MIN_PYTHON_VERSION:
            return CheckItem("Python", True, f"当前版本 {version}")
        required = ".".join(str(part) for part in MIN_PYTHON_VERSION)
        return CheckItem("Python", False, f"当前版本 {version}，最低需要 {required}", "安装 Python 3.11+。")

    def _check_command(self, name: str, command: str, fix: str) -> CheckItem:
        path = self.which(command)
        if path:
            return CheckItem(name, True, f"已找到 {path}")
        return CheckItem(name, False, f"未找到命令 {command}", fix)

    def _check_motion_package_json(self) -> CheckItem:
        package_json = self._motion_app_dir.parent / "package.json"
        if package_json.exists():
            return CheckItem("HTML Motion package", True, str(package_json))
        return CheckItem(
            "HTML Motion package",
            False,
            "缺少 HTML Motion 子项目 package.json",
            "确认项目完整下载，包含 core/infra/motion/package.json。",
        )

    def _check_motion_template(self) -> CheckItem:
        index_html = self._motion_app_dir / "index.html"
        if index_html.exists():
            return CheckItem("HTML Motion template", True, str(index_html))
        return CheckItem(
            "HTML Motion template",
            False,
            "缺少 HTML Motion 网页模板 index.html",
            "确认项目完整下载，包含 core/infra/motion/app/index.html。",
        )

    def _check_motion_skill_bundle(self) -> CheckItem:
        required_files = (
            "motion-core/SKILL.md",
            "motion-animation/SKILL.md",
            "motion-creative/SKILL.md",
            "motion-core/references/rendering.md",
        )
        missing = [
            rel_path
            for rel_path in required_files
            if not (self._motion_skill_dir / rel_path).exists()
        ]
        if not missing:
            return CheckItem("Step4 HTML Motion skills", True, str(self._motion_skill_dir))
        return CheckItem(
            "Step4 HTML Motion skills",
            False,
            "缺少: " + ", ".join(missing),
            "确认项目完整下载，包含 skills/step4/ 下的 HTML Motion skill 文件。",
        )

    def _check_python_packages(self) -> CheckItem:
        missing = []
        for package_name in self._pyproject_package_names():
            import_name = PACKAGE_IMPORT_NAMES.get(package_name, package_name.replace("-", "_"))
            if not self.import_checker(import_name):
                missing.append(package_name)

        if not missing:
            return CheckItem("Python packages", True, "pyproject.toml 中的依赖包已安装并可导入")
        return CheckItem(
            "Python packages",
            False,
            "缺少: " + ", ".join(missing),
            "运行 pip install -e . 或 pip install . 安装依赖。",
        )

    def _check_env_file(self) -> CheckItem:
        env_path = self.repo_root / ".env"
        example_path = self.repo_root / ".env.example"
        if env_path.exists():
            return CheckItem("Environment file", True, ".env 已存在")
        if example_path.exists():
            return CheckItem(
                "Environment file",
                False,
                "缺少 .env，但存在 .env.example",
                "复制 .env.example 为 .env 并填入密钥。",
            )
        return CheckItem("Environment file", False, "缺少 .env 和 .env.example", "确认项目文件完整。")

    def _check_music_dir(self) -> CheckItem:
        music_dir = self.repo_root / "music"
        if music_dir.exists():
            return CheckItem("Music directory", True, "music 目录存在")
        return CheckItem("Music directory", False, "缺少 music 目录", "创建 music 目录，或关闭默认背景音乐。")

    def _check_input_dir(self) -> CheckItem:
        input_dir = self.repo_root / "input"
        if input_dir.exists():
            return CheckItem("Input directory", True, "input 目录存在")
        return CheckItem("Input directory", False, "缺少 input 目录", "创建 input 目录并放入待处理文档。")

    def _check_api_keys(self) -> CheckItem:
        env_values = self._load_env_values()
        required_groups = self._required_key_groups()
        missing = []
        for label, key_names in required_groups:
            if not any(env_values.get(key) for key in key_names):
                missing.append(f"{label}: {' 或 '.join(key_names)}")

        if not missing:
            return CheckItem("API keys", True, "当前配置所需密钥已填写")
        return CheckItem(
            "API keys",
            False,
            "缺少 " + "; ".join(missing),
            "编辑 .env，填入当前配置所需的服务密钥。",
        )

    @property
    def _motion_app_dir(self) -> Path:
        return self.repo_root / "core" / "infra" / "motion" / "app"

    @property
    def _motion_skill_dir(self) -> Path:
        return self.repo_root / "skills" / "step4"

    def _pyproject_package_names(self) -> Iterable[str]:
        pyproject = self.repo_root / "pyproject.toml"
        if not pyproject.exists():
            return []
        content = pyproject.read_text(encoding="utf-8")
        match = re.search(r"dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL)
        if not match:
            return []
        deps_block = match.group(1)
        package_names = []
        for raw_line in deps_block.splitlines():
            line = raw_line.strip().strip(",").strip('"').strip("'")
            if not line or line.startswith("#"):
                continue
            # Extract package name (ignoring extras and version, e.g. volcengine-python-sdk[ark]>=1.0.94 -> volcengine-python-sdk)
            pkg_match = re.match(r"([A-Za-z0-9_.-]+)", line)
            if pkg_match:
                package_names.append(pkg_match.group(1).lower())
        return package_names

    def _load_env_values(self) -> dict[str, str]:
        values = {key: value for key, value in os.environ.items() if value}
        env_path = self.repo_root / ".env"
        if not env_path.exists():
            return values
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            cleaned_value = value.strip().strip('"').strip("'")
            if cleaned_value and not cleaned_value.startswith("你的") and cleaned_value != "your_key":
                values[key.strip()] = cleaned_value
        return values

    def _required_key_groups(self) -> list[tuple[str, tuple[str, ...]]]:
        from core import config as runtime_config

        providers = [
            ("步骤1 LLM", getattr(runtime_config, "LLM_SERVER_STEP1", "")),
            ("步骤2 LLM", getattr(runtime_config, "LLM_SERVER_STEP2", "")),
            ("步骤4画面LLM", getattr(runtime_config, "LLM_SERVER_STEP4", "")),
            ("步骤4画面生成", getattr(runtime_config, "IMAGE_SERVER", "")),
            ("封面生成", getattr(runtime_config, "COVER_IMAGE_SERVER", "")),
            ("步骤3语音合成", "bytedance"),
        ]
        groups = []
        seen = set()
        for label, provider in providers:
            provider_key = str(provider or "").strip().lower()
            key_names = PROVIDER_KEY_GROUPS.get(provider_key)
            if not key_names:
                continue
            dedupe_key = (label, key_names)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            groups.append((label, key_names))
        return groups

    @staticmethod
    def _can_import(import_name: str) -> bool:
        return importlib.util.find_spec(import_name) is not None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查智能视频制作系统部署依赖")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--require-api-keys", action="store_true", help="同时检查当前配置需要的 API 密钥")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    report = DependencyChecker(repo_root=Path(args.repo_root)).check(require_api_keys=args.require_api_keys)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(report.format_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
