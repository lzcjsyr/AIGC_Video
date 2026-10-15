"""Project-owned references for HTML, GSAP and Three.js clips."""
from pathlib import Path
from core.resources import skills_dir

STEP4_MOTION_SKILL_DIR_NAMES = ('motion-core', 'motion-animation', 'motion-creative')
STEP4_MAX_REFERENCE_READS = 3
STEP4_MOTION_RECIPES = tuple((name, f'motion-animation/rules/{name}.md') for name in (
    'counter_burst', 'split_reveal', 'cause_flow', 'camera_push', 'card_morph', 'radial_orbit', 'marker_trace'))
STEP4_OPTIONAL_REFERENCES = (
    ('Three.js、相机和模型动画', 'motion-core/references/three.md'),
    ('确定性与导出检查', 'motion-core/references/rendering.md'),
    ('字体和阅读层级', 'motion-creative/references/typography.md'),
)

def step4_motion_skills_root():
    return skills_dir() / 'step4'

def default_step4_motion_skill_dir():
    return step4_motion_skills_root() / 'motion-core'

def step4_motion_skill_dirs(skills_root=None):
    root = Path(skills_root) if skills_root else step4_motion_skills_root()
    return [root / name for name in STEP4_MOTION_SKILL_DIR_NAMES]

def build_step4_motion_skill_path_context(skill_dir=None):
    root = Path(skill_dir).parent if skill_dir else step4_motion_skills_root()
    return '\n'.join([
        f'STEP4_SKILLS_ROOT={root}',
        '直接编写本段 HTML；仅按需读取参考，最多 3 个。',
        *[f'- {name}: {root / relative}' for name, relative in STEP4_MOTION_RECIPES + STEP4_OPTIONAL_REFERENCES],
        *[f'- entry_path: {p / "SKILL.md"}' for p in step4_motion_skill_dirs(root)],
    ])
