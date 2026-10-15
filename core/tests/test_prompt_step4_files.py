from pathlib import Path



PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def test_static_visual_prompts_are_named_for_step4():
    assert (PROMPTS_DIR / "step4_image_templates.yaml").exists()
    assert (PROMPTS_DIR / "step4_safety.md").exists()
    assert (PROMPTS_DIR / "step4_styles.yaml").exists()

    assert not (PROMPTS_DIR / "step3_description.md").exists()
    assert not (PROMPTS_DIR / "step3_safety.md").exists()
    assert not (PROMPTS_DIR / "step3_styles.yaml").exists()


def test_step4_image_yaml_keeps_original_template_and_offers_multiple_choices():
    from core.prompts import (
        DEFAULT_STEP4_IMAGE_PROMPT_TEMPLATE,
        STEP4_IMAGE_DESCRIPTION_PROMPT_TEMPLATES,
        STEP4_IMAGE_PROMPT_TEMPLATE_DEFINITIONS,
    )

    original_template = """为视频文案的每一段生成一张配图，用图示为主、文字为辅，帮助读者更好地理解内容。
文字规范：只需要2到4个突出段落主旨的关键词。每个词都以极度简短为第一原则。关键词与背景颜色形成鲜明反差，确保可读性。
配图规范：文字必须为中文，位置只能出现在图片的上半部分。整体画面应匹配内容主题，简约美观，不得出现诡异、恐怖的元素。

以下是全文概述，不是展示的重点：
{{
{summary}
}}

以下是需要生成配图的文案内容，信息的核心：
{{
{segment}
}}

请严格遵循以下画面风格设定：
{{
{style_block}
}}
"""

    assert DEFAULT_STEP4_IMAGE_PROMPT_TEMPLATE == "keywords"
    assert STEP4_IMAGE_DESCRIPTION_PROMPT_TEMPLATES["keywords"] == original_template
    assert set(STEP4_IMAGE_DESCRIPTION_PROMPT_TEMPLATES) == {"keywords", "pure_images"}
    assert STEP4_IMAGE_PROMPT_TEMPLATE_DEFINITIONS["keywords"]["label"] == "原有图示关键词模板"
    assert STEP4_IMAGE_PROMPT_TEMPLATE_DEFINITIONS["pure_images"]["description"]
    for template in STEP4_IMAGE_DESCRIPTION_PROMPT_TEMPLATES.values():
        rendered = template.format(summary="全文", segment="本段", style_block="风格")
        assert "全文" in rendered
        assert "本段" in rendered
        assert "风格" in rendered


def test_motion_agent_has_dedicated_step4_prompt_file():
    prompt_path = PROMPTS_DIR / "step4_motion_agent.md"
    assert prompt_path.exists()
    assert (PROMPTS_DIR / "step4_motion_styles.yaml").exists()
    prompt = prompt_path.read_text(encoding="utf-8")
    for token in ["{skill_path_context}", "{style_context}", "{payload_json}", "window.clip", "renderAt", "ready", "vendor/", "python render.py check --snapshots", "visualKeywords"]:
        assert token in prompt
    assert "hyperframes" not in prompt.lower()
    assert "CDN" in prompt


def test_step4_motion_prompt_is_loaded_from_prompt_file(monkeypatch):
    from core.infra.ai import claude_agent

    monkeypatch.setattr(
        claude_agent,
        "STEP4_MOTION_AGENT_PROMPT_TEMPLATE",
        "PROMPT_FILE_MARKER\n{skill_path_context}\n{style_context}\n{payload_json}\n{target_index_html_path}",
    )

    prompt = claude_agent._build_step4_motion_prompt(
        segment_payload={"index": 1, "durationSeconds": 1.25},
        style_preset="data_driven",
        skill_path_context="STEP4_SKILLS_ROOT=/dynamic/project/skills/step4",
        target_index_html_path="/test/path/index.html",
    )

    assert prompt.startswith("PROMPT_FILE_MARKER")
    assert "HyperFrames rules" not in prompt
    assert "STEP4_SKILLS_ROOT=/dynamic/project/skills/step4" in prompt
    assert "data_driven" in prompt
    assert "Swiss Pulse" in prompt
    assert '"durationSeconds": 1.25' in prompt
    assert "/test/path/index.html" in prompt


def test_step4_skill_context_points_at_recipes_and_keeps_skills_optional(tmp_path):
    from core.infra.motion.skill_loader import build_step4_motion_skill_path_context
    skills_root = tmp_path / "skills" / "step4"
    context = build_step4_motion_skill_path_context(skills_root / "motion-core")
    assert f"STEP4_SKILLS_ROOT={skills_root}" in context
    assert f"counter_burst: {skills_root / 'motion-animation/rules/counter_burst.md'}" in context
    assert f"entry_path: {skills_root / 'motion-core/SKILL.md'}" in context
    assert "最多 3 个" in context
    assert "hyperframes" not in context.lower()
