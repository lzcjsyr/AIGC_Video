from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from core.resources import skills_dir


STEP4_HYPERFRAMES_SKILL_DIR_NAMES = (
    "hyperframes",
    "hyperframes-core",
    "hyperframes-animation",
    "hyperframes-creative",
    "hyperframes-cli",
    "hyperframes-media",
    "hyperframes-registry",
    "general-video",
)

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)


def default_step4_hyperframes_skill_dir() -> Path:
    return skills_dir() / "step4" / "hyperframes"


def step4_hyperframes_skills_root() -> Path:
    return skills_dir() / "step4"


def step4_hyperframes_skill_dirs(skills_root: str | Path | None = None) -> list[Path]:
    root = Path(skills_root) if skills_root else step4_hyperframes_skills_root()
    return [root / name for name in STEP4_HYPERFRAMES_SKILL_DIR_NAMES]


def _step4_skill_entry_paths(skills_root: Path) -> list[Path]:
    ordered_paths = [skills_root / name / "SKILL.md" for name in STEP4_HYPERFRAMES_SKILL_DIR_NAMES]
    known = {path.resolve() for path in ordered_paths if path.exists()}
    extra_paths = [
        path
        for path in sorted(skills_root.glob("*/SKILL.md"))
        if path.resolve() not in known
    ]
    return [path for path in ordered_paths if path.exists()] + extra_paths


def _read_skill_frontmatter(skill_path: Path) -> dict[str, object]:
    text = skill_path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    data = yaml.safe_load(match.group(1)) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _format_skill_metadata(value: object) -> str:
    if value in (None, "", {}, []):
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def build_step4_hyperframes_skill_path_context(skill_dir: str | Path | None = None) -> str:
    skills_root = Path(skill_dir).parent if skill_dir else step4_hyperframes_skills_root()
    skill_sections: list[str] = []
    for entry_path in _step4_skill_entry_paths(skills_root):
        frontmatter = _read_skill_frontmatter(entry_path)
        name = str(frontmatter.get("name") or entry_path.parent.name).strip()
        description = str(frontmatter.get("description") or "").strip()
        metadata = _format_skill_metadata(frontmatter.get("metadata"))
        lines = [
            f"- name: {name}",
            f"  entry_path: {entry_path}",
        ]
        if description:
            lines.append(f"  description: {description}")
        if metadata:
            lines.append(f"  metadata: {metadata}")
        skill_sections.append("\n".join(lines))
    skill_lines = "\n".join(skill_sections) if skill_sections else "- 未发现可用 Step4 skills"
    return "\n".join(
        [
            f"STEP4_SKILLS_ROOT={skills_root}",
            "",
            "可用 Step4 Skills：",
            skill_lines,
            "",
            "读取规则：",
            "- 写 HTML 前必须先根据 name/description 判断本任务需要哪些 skill；不要只依赖记忆或自行猜测。",
            "- 当某个 skill 适用时，必须使用 Read 工具读取它的 entry_path；读取 SKILL.md 后，再按它内部引用的相对路径继续读取必要 reference。",
            "- 禁止跳过该 skill 的 SKILL.md 直接读取它的 references、palettes、adapters 或 rules 文件。",
            "- 如果读取了某个目录下的 reference/palette/adapter/rule 文件，必须已经先读取同目录对应的 SKILL.md。",
            "- 不要一次性读取全部 reference；只读取与当前段落生成、风格、动画、CLI 检查直接相关的文件。",
            "- 所有官方 HyperFrames skill 相对路径都必须基于 STEP4_SKILLS_ROOT 拼接；风格映射里的 `hyperframes-creative/...`、`hyperframes-animation/...` 等包名路径都不是项目根路径。",
            "- 禁止读取或猜测 `skills/hyperframes-creative/...`、`skills/hyperframes-animation/...`、`skills/hyperframes-core/...`；本项目真实路径包含 `skills/step4/`。",
        ]
    ).strip()
