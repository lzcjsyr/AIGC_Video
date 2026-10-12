"""
智能视频制作系统 - 中文提示词加载模块
动态从根目录 /prompts 文件夹读取 Markdown (.md) 提示词模板和 YAML (.yaml) 风格预设
"""

import os
import re
import string
import yaml

from core.resources import prompts_dir

def _load_prompt_file(filename: str) -> str:
    path = os.path.join(prompts_dir(), filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"提示词模板文件未找到: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _load_yaml_file(filename: str) -> dict:
    path = os.path.join(prompts_dir(), filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"YAML配置文件未找到: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_prompt_template_definitions(filename: str) -> dict[str, dict[str, str]]:
    """Load and validate human-readable prompt template definitions from YAML."""
    raw_definitions = _load_yaml_file(filename)
    if not isinstance(raw_definitions, dict) or not raw_definitions:
        raise ValueError(f"提示词模板文件必须包含至少一个模板: {filename}")

    definitions: dict[str, dict[str, str]] = {}
    required_keys = {"label", "description", "template"}
    for name, definition in raw_definitions.items():
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", name):
            raise ValueError(f"提示词模板 ID 格式无效: {name}")
        if not isinstance(definition, dict):
            raise ValueError(f"提示词模板 {name} 必须是包含 label、description、template 的对象")
        actual_keys = set(definition)
        if actual_keys != required_keys:
            raise ValueError(
                f"提示词模板 {name} 的字段必须且只能为: {sorted(required_keys)}，实际为: {sorted(actual_keys)}"
            )
        if not all(isinstance(definition[key], str) and definition[key].strip() for key in required_keys):
            raise ValueError(f"提示词模板 {name} 的 label、description、template 均不能为空")
        template = definition["template"]
        fields = {
            field_name
            for _, field_name, _, _ in string.Formatter().parse(template)
            if field_name
        }
        required_fields = {"summary", "segment", "style_block"}
        if fields != required_fields:
            raise ValueError(
                f"提示词模板 {name} 的变量必须且只能为: {sorted(required_fields)}，实际为: {sorted(fields)}"
            )
        definitions[name] = {
            "label": definition["label"].strip(),
            "description": definition["description"].strip(),
            "template": template,
        }
    return definitions

# ================================================================================
# 动态加载提示词模板
# ================================================================================
STEP1_AGENT_PROMPT_TEMPLATE = _load_prompt_file("step1_agent.md")
STEP1_5_SEGMENT_PROMPT_TEMPLATE = _load_prompt_file("step1_5_segment.md")
description_summary_system_prompt = _load_prompt_file("step2_summary.md")
STEP4_IMAGE_PROMPT_SAFETY_TEMPLATE = _load_prompt_file("step4_safety.md")
STEP4_IMAGE_PROMPT_TEMPLATE_DEFINITIONS = _load_prompt_template_definitions("step4_image_templates.yaml")
STEP4_IMAGE_DESCRIPTION_PROMPT_TEMPLATES = {
    name: definition["template"]
    for name, definition in STEP4_IMAGE_PROMPT_TEMPLATE_DEFINITIONS.items()
}
DEFAULT_STEP4_IMAGE_PROMPT_TEMPLATE = (
    "keywords" if "keywords" in STEP4_IMAGE_PROMPT_TEMPLATE_DEFINITIONS
    else next(iter(STEP4_IMAGE_PROMPT_TEMPLATE_DEFINITIONS))
)
STEP4_IMAGE_DESCRIPTION_PROMPT_TEMPLATE = STEP4_IMAGE_DESCRIPTION_PROMPT_TEMPLATES[
    DEFAULT_STEP4_IMAGE_PROMPT_TEMPLATE
]
STEP4_HYPERFRAMES_AGENT_PROMPT_TEMPLATE = _load_prompt_file("step4_hyperframes_agent.md")
STEP4_HYPERFRAMES_PROMPT_VERSION = "2026-06-26-phone-readable-v9"
IMAGE_PROMPT_SAFETY_TEMPLATE = STEP4_IMAGE_PROMPT_SAFETY_TEMPLATE
IMAGE_DESCRIPTION_PROMPT_TEMPLATE = STEP4_IMAGE_DESCRIPTION_PROMPT_TEMPLATE
COVER_IMAGE_PROMPT_TEMPLATE = _load_prompt_file("step6_cover.md")
STEP4_OPENING_BG_PROMPT_TEMPLATE = _load_prompt_file("step4_opening_bg.md")
OPENING_BG_PROMPT_TEMPLATE = STEP4_OPENING_BG_PROMPT_TEMPLATE


# ================================================================================
# 动态加载图像与封面预设风格
# ================================================================================
STEP4_IMAGE_STYLE_PRESETS = _load_yaml_file("step4_styles.yaml")
STEP4_HYPERFRAMES_STYLE_PRESETS = _load_yaml_file("step4_hyperframes_styles.yaml")
IMAGE_STYLE_PRESETS = STEP4_IMAGE_STYLE_PRESETS
COVER_IMAGE_STYLE_PRESETS = _load_yaml_file("step6_styles.yaml")

# ================================================================================
# 提示词构造函数
# ================================================================================
def get_step4_image_description_prompt_template(template_name: str | None = None) -> str:
    """Return a configured step-4 image prompt template or fail with valid choices."""
    name = (template_name or DEFAULT_STEP4_IMAGE_PROMPT_TEMPLATE).strip()
    template = STEP4_IMAGE_DESCRIPTION_PROMPT_TEMPLATES.get(name)
    if template is None:
        choices = ", ".join(STEP4_IMAGE_DESCRIPTION_PROMPT_TEMPLATES)
        raise ValueError(f"不支持的步骤4生图提示词模板: {name}，可选: {choices}")
    return template


def build_step4_hyperframes_style_context(style_preset: str, skills_root: str | os.PathLike | None = None) -> str:
    """构建第四步 HyperFrames 官方风格映射上下文。"""
    style_id = (style_preset or "data_driven").strip()
    style = STEP4_HYPERFRAMES_STYLE_PRESETS.get(style_id) or STEP4_HYPERFRAMES_STYLE_PRESETS.get("data_driven", {})
    references = style.get("references") or []
    if skills_root:
        root = os.fspath(skills_root)
        reference_lines = "\n".join(
            f"- {item} -> {os.path.join(root, item.split('#', 1)[0])}"
            for item in references
        ) if references else "- 无"
    else:
        reference_lines = "\n".join(f"- {item}" for item in references) if references else "- 无"
    return "\n".join(
        [
            f"用户选择的业务风格：{style_id}",
            f"显示名称：{style.get('label', style_id)}",
            f"官方 HyperFrames 风格：{style.get('official_style', 'Swiss Pulse')}",
            f"官方调色板：{style.get('palette', 'dark-premium')}",
            f"适用场景：{style.get('best_for', '')}",
            "必须优先参考：",
            reference_lines,
        ]
    ).strip()


def build_step1_agent_prompt(
    input_file: str,
    output_json: str,
    text_dir: str,
    skill_path: str,
    extra_requirements: str = "",
) -> str:
    """构建 Claude Agent 步骤1 生成原始文稿所需的系统提示词。"""
    extra_requirements = (extra_requirements or "").strip() or "无"
    return STEP1_AGENT_PROMPT_TEMPLATE.format(
        input_file=input_file,
        output_json=output_json,
        text_dir=text_dir,
        skill_path=skill_path,
        extra_requirements=extra_requirements,
    )

# ================================================================================
# 导出配置
# ================================================================================
__all__ = [
    'STEP1_AGENT_PROMPT_TEMPLATE',
    'STEP1_5_SEGMENT_PROMPT_TEMPLATE',
    'build_step1_agent_prompt',
    'description_summary_system_prompt',
    'IMAGE_DESCRIPTION_PROMPT_TEMPLATE',
    'IMAGE_PROMPT_SAFETY_TEMPLATE',
    'IMAGE_STYLE_PRESETS',
    'DEFAULT_STEP4_IMAGE_PROMPT_TEMPLATE',
    'STEP4_IMAGE_PROMPT_TEMPLATE_DEFINITIONS',
    'STEP4_IMAGE_DESCRIPTION_PROMPT_TEMPLATES',
    'STEP4_IMAGE_DESCRIPTION_PROMPT_TEMPLATE',
    'get_step4_image_description_prompt_template',
    'STEP4_IMAGE_PROMPT_SAFETY_TEMPLATE',
    'STEP4_IMAGE_STYLE_PRESETS',
    'STEP4_HYPERFRAMES_STYLE_PRESETS',
    'STEP4_HYPERFRAMES_PROMPT_VERSION',
    'build_step4_hyperframes_style_context',
    'STEP4_HYPERFRAMES_AGENT_PROMPT_TEMPLATE',
    'COVER_IMAGE_STYLE_PRESETS',
    'COVER_IMAGE_PROMPT_TEMPLATE',
    'STEP4_OPENING_BG_PROMPT_TEMPLATE',
    'OPENING_BG_PROMPT_TEMPLATE',
]
