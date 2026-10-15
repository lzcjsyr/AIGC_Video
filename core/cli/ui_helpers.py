"""
CLI界面特定的交互函数和主要业务逻辑
提供命令行界面的用户交互和完整的CLI功能

功能模块:
- CLI日志配置和用户交互界面
- 项目选择器、文件选择器、步骤显示等UI组件
- CLI主要业务逻辑和流程控制
- 从utils.py迁移而来的UI相关函数，保持CLI界面的简洁和用户友好
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.prompts import STEP4_MOTION_STYLE_PRESETS
from core.shared import load_json_file


_UNSET = object()


def setup_cli_logging(log_level=logging.INFO):
    """配置CLI专用的日志设置"""
    
    # 清除可能存在的旧配置
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # CLI日志保存到cli目录下
    cli_dir = Path(__file__).parent
    log_file = cli_dir / 'cli.log'
    
    # 配置日志格式（CLI友好的简洁格式）
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [CLI] %(levelname)s - %(message)s',
        datefmt='%H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # 控制台输出
        ]
    )
    
    # 设置AIGC_Video logger
    logger = logging.getLogger('AIGC_Video')
    logger.setLevel(log_level)
    
    # 降低第三方库的噪声日志
    for lib_name in [
        "pdfminer", "pdfminer.pdffont", "pdfminer.pdfinterp", "pdfminer.cmapdb",
        "urllib3", "requests", "PIL"
    ]:
        logging.getLogger(lib_name).setLevel(logging.ERROR)
    
    logger.info("CLI日志配置完成")
    return logger


def interactive_project_selector(output_dir: str = "output") -> Optional[str]:
    """
    交互式项目选择器（从 output/ 选择已有项目文件夹）
    """
    from core.pipeline.scanner import scan_output_projects
    
    print("\n📂 打开现有项目")
    print("正在扫描 output 目录...")
    projects = scan_output_projects(output_dir)
    display_project_menu(projects)
    return get_user_project_selection(projects)


def display_project_menu(projects: List[Dict[str, Any]]) -> None:
    """
    显示项目菜单列表
    """
    if not projects:
        print("❌ 未找到任何项目文件夹")
        return
    
    print_section("发现以下项目", "📁", "=")
    for i, proj in enumerate(projects, 1):
        modified_date = proj['modified_time'].strftime('%Y-%m-%d %H:%M')
        print(f"{i:2d}. {proj['name']}")
        print(f"     修改时间: {modified_date}")
        if i % 10 == 0:
            print()
    print("=" * 60)  # 结束分隔线


def get_user_project_selection(projects: List[Dict[str, Any]]) -> Optional[str]:
    """
    获取用户项目选择
    """
    if not projects:
        return None
    
    while True:
        try:
            choice = input(f"请选择要打开的项目 (1-{len(projects)}) 或输入 'q' 返回上一级: ").strip()
            if choice.lower() == 'q':
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(projects):
                selected = projects[idx]
                print(f"\n✅ 您选择了项目: {selected['name']}")
                return selected['path']
            else:
                print(f"❌ 无效选择，请输入 1-{len(projects)} 之间的数字")
        except ValueError:
            print("❌ 请输入有效数字")
        except KeyboardInterrupt:
            print("\n操作已取消")
            return None


def display_project_progress_and_select_step(progress) -> Optional[float]:
    """
    显示项目完整进度并允许用户选择要重新执行的步骤
    
    Args:
        progress: detect_project_progress 返回的进度字典
        
    Returns:
        Optional[float]: 选择的步骤编号，None表示退出
    """
    # 步骤定义 - 使用实际状态而不是简单的完成标记
    has_description = progress.get('has_description', False)
    step2_done = has_description

    # 定义每个步骤的三种状态: "completed" / "in_progress" / "not_started"
    steps = [
        (1, "内容生成",
         "completed" if progress.get('has_raw', False) else "not_started"),
        (1.5, "脚本分段",
         "completed" if progress.get('has_script', False) else "not_started"),
        (2, "描述小结",
         "completed" if step2_done else "not_started"),
        (3, "语音合成",
         "completed" if progress.get('audio_ok', False) else
         ("in_progress" if progress.get('audio_in_progress', False) else "not_started")),
        (4, "画面生成",
         "completed" if progress.get('images_ok', False) else
         ("in_progress" if progress.get('images_in_progress', False) else "not_started")),
        (5, "视频合成",
         "completed" if progress.get('has_final_video', False) else "not_started"),
        (6, "封面生成",
         "completed" if progress.get('has_cover', False) else "not_started")
    ]

    current_step = progress.get('current_step', 0)

    print("\n📊 项目进度状态")
    print("=" * 60)

    # 显示步骤状态 - 基于实际状态而非简单的数字比较
    for step_num, step_name, step_status in steps:
        if step_status == "completed":
            status = "✅ 已完成"
        elif step_status == "in_progress":
            status = "⏳ 进行中"
        else:
            status = "⭕ 未开始"

        print(f"步骤 {step_num:>3}: {step_name:<10} {status}")
    
    print("=" * 60)
    
    # 创建步骤号到步骤名的映射
    step_names_dict = {step_num: step_name for step_num, step_name, _ in steps}
    current_step_name = step_names_dict.get(current_step, '未知')
    print(f"当前进度：步骤 {current_step} - {current_step_name}")
    
    # 确定允许的步骤：支持步骤3和4的独立执行
    allowed_steps = []

    # 基于已完成的步骤确定可重做的步骤
    if progress.get('has_raw', False):
        allowed_steps.append(1)    # 允许重做内容生成
    if progress.get('has_script', False):
        allowed_steps.append(1.5)  # 允许重做脚本分段
    if step2_done:
        allowed_steps.append(2)    # 允许重做描述小结
    if progress.get('audio_ok', False):
        allowed_steps.append(3)    # 允许重做语音合成
    if progress.get('images_ok', False):
        allowed_steps.append(4)    # 允许重做画面生成
    if progress.get('has_final_video', False):
        allowed_steps.append(5)    # 允许重做视频合成

    # 添加可执行的下一步
    if not progress.get('has_raw', False):
        allowed_steps.append(1)    # 可执行内容生成
    if not progress.get('has_script', False) and progress.get('has_raw', False):
        allowed_steps.append(1.5)  # 可执行脚本分段
    if not step2_done and progress.get('has_script', False):
        allowed_steps.append(2)    # 可执行描述小结
    if not progress.get('audio_ok', False) and progress.get('has_script', False):
        allowed_steps.append(3)    # 可执行语音合成（只需script.json）
    if not progress.get('images_ok', False) and step2_done and progress.get('audio_ok', False):
        allowed_steps.append(4)    # 可执行画面生成（需要描述小结和语音时长）
    if not progress.get('has_final_video', False) and progress.get('images_ok', False) and progress.get('audio_ok', False):
        allowed_steps.append(5)    # 可执行视频合成（需要图像和音频都完成）
    if progress.get('has_raw', False):
        allowed_steps.append(6)    # 内容生成完成后即可生成封面
    
    allowed_steps.sort()
    
    print(f"\n可执行步骤：{', '.join(map(str, allowed_steps))} (输入 q 退出)")
    
    while True:
        try:
            choice = input("请输入步骤号: ").strip()
            
            if choice.lower() == 'q':
                return None
            
            try:
                step_num = float(choice)
                if step_num in allowed_steps:
                    step_name = step_names_dict.get(step_num, f"步骤{step_num}")
                    print(f"\n✅ 您选择了：步骤 {step_num} - {step_name}")
                    return step_num
                else:
                    print(f"❌ 步骤 {step_num} 不可执行。可选步骤：{', '.join(map(str, allowed_steps))}")
            except ValueError:
                print(f"❌ 无效输入。请输入有效步骤号：{', '.join(map(str, allowed_steps))}")
            
        except KeyboardInterrupt:
            print("\n操作已取消")
            return None


def prompt_choice(message: str, options: List[str], default_index: int = 0) -> Optional[str]:
    """通用选项选择器，返回所选项文本。
    支持输入序号或精确匹配选项文本（不区分大小写）。
    """
    try:
        while True:
            print(f"\n{message}（输入 q 返回上一级）")
            for i, opt in enumerate(options, 1):
                prefix = "*" if (i - 1) == default_index else " "
                print(f" {prefix} {i}. {opt}")
            raw = input(f"请输入序号 (默认 {default_index+1}): ").strip()
            if raw == "":
                return options[default_index]
            if raw.lower() == 'q':
                return None
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            # 文本匹配
            for opt in options:
                if raw.lower() == opt.lower():
                    return opt
            print("无效输入，请重试。")
    except KeyboardInterrupt:
        print("\n操作已取消")
        return options[default_index]


def prompt_image_style_choice(style_type: str = "segment") -> Optional[str]:
    """
    提示用户选择图像风格

    Args:
        style_type: "segment" 或 "cover"

    Returns:
        选中的风格ID，如 "style02" 或 "cover06"
    """
    from core.prompts import IMAGE_STYLE_PRESETS, COVER_IMAGE_STYLE_PRESETS
    import core.config as config
    if style_type == "segment":
        presets = IMAGE_STYLE_PRESETS
        message = "请选择段落图片风格"
        default_key = config.IMAGE_STYLE_PRESET
    else:
        presets = COVER_IMAGE_STYLE_PRESETS
        message = "请选择封面图片风格"
        default_key = config.COVER_IMAGE_STYLE

    # 构建选项列表
    options = [f"{key}: {value}" for key, value in presets.items()]

    # 获取默认索引
    preset_keys = list(presets.keys())
    default_idx = preset_keys.index(default_key) if default_key in preset_keys else 0

    # 用户选择
    selected = prompt_choice(message, options, default_index=default_idx)

    if selected is None:
        return None

    # 提取风格ID
    style_id = selected.split(":")[0].strip()
    return style_id


def prompt_visual_mode_choice(default_mode: str = "static_image") -> Optional[str]:
    """提示用户选择第四步画面生成模式。"""
    modes = [
        ("static_image", "静态图片"),
        ("motion_agent", "HTML 动态视频"),
        ("mixed", "混合模式（按 script.json 的 visualizer 字段选择）"),
    ]
    default_mode = (default_mode or "static_image").strip().lower()
    default_idx = next((idx for idx, (mode, _label) in enumerate(modes) if mode == default_mode), 0)
    options = [f"{mode}: {label}" for mode, label in modes]
    selected = prompt_choice("请选择画面生成模式", options, default_index=default_idx)
    if selected is None:
        return None
    return selected.split(":", 1)[0].strip()


def prompt_motion_style_choice(default_style: str = "data_driven") -> Optional[str]:
    """提示用户选择 HTML / Three.js 动态画面风格。"""
    styles = [
        (style_id, str(style.get("label") or style_id))
        for style_id, style in STEP4_MOTION_STYLE_PRESETS.items()
    ]
    default_style = (default_style or "data_driven").strip().lower()
    default_idx = next((idx for idx, (style, _label) in enumerate(styles) if style == default_style), 0)
    options = [f"{style}: {label}" for style, label in styles]
    selected = prompt_choice("请选择 HTML / Three.js 动态画面风格", options, default_index=default_idx)
    if selected is None:
        return None
    return selected.split(":", 1)[0].strip()


def display_file_menu(files: List[Dict[str, Any]]) -> None:
    """
    显示文件选择菜单

    Args:
        files: 文件信息列表
    """
    print_section("发现以下可处理的文件或文件夹", "📚", "=")
    
    if not files:
        print("❌ 在input文件夹中未找到PDF、EPUB、MOBI、AZW3、MD、TXT、DOCX、DOC文件或文件夹")
        print("请将要处理的PDF、EPUB、MOBI、AZW3、MD、TXT、DOCX、DOC文件或文件夹放入input文件夹中")
        return
    
    for i, file_info in enumerate(files, 1):
        if file_info.get('is_directory'):
            file_type = "📁 文件夹"
        elif file_info['extension'] == '.epub':
            file_type = "📖 EPUB"
        elif file_info['extension'] == '.pdf':
            file_type = "📄 PDF"
        elif file_info['extension'] == '.mobi':
            file_type = "📱 MOBI"
        elif file_info['extension'] == '.azw3':
            file_type = "📗 AZW3"
        elif file_info['extension'] == '.md':
            file_type = "📝 MD"
        elif file_info['extension'] == '.txt':
            file_type = "📝 TXT"
        elif file_info['extension'] == '.docx':
            file_type = "📄 DOCX"
        elif file_info['extension'] == '.doc':
            file_type = "📄 DOC"
        else:
            file_type = "📄 FILE"
        modified_date = file_info['modified_time'].strftime('%Y-%m-%d %H:%M')
        
        print(f"{i:2}. {file_type} {file_info['name']}")
        print(f"     大小: {file_info['size_formatted']} | 修改时间: {modified_date}")
        print()


def get_user_file_selection(files: List[Dict[str, Any]]) -> Optional[str]:
    """
    获取用户的文件选择
    
    Args:
        files: 文件信息列表
    
    Returns:
        Optional[str]: 选择的文件路径，如果用户取消则返回None
    """
    if not files:
        return None
    
    while True:
        try:
            print("=" * 60)
            choice = input(f"请选择要处理的文件或文件夹 (1-{len(files)}) 或输入 'q' 返回上一级: ").strip()
            
            if choice.lower() == 'q':
                print("👋 返回上一级")
                return None
            
            file_index = int(choice) - 1
            
            if 0 <= file_index < len(files):
                selected_file = files[file_index]
                print(f"\n✅ 您选择了: {selected_file['name']}")
                if selected_file.get("is_directory"):
                    print("   类型: 文件夹")
                else:
                    print(f"   文件大小: {selected_file['size_formatted']}")
                    print(f"   文件类型: {selected_file['extension'].upper()}")
                # 直接返回所选文件路径，无需再次确认
                return selected_file['path']
            else:
                print(f"❌ 无效选择，请输入 1-{len(files)} 之间的数字")
                
        except ValueError:
            print("❌ 请输入有效的数字")
        except KeyboardInterrupt:
            print("\n\n👋 程序已取消")
            return None


def interactive_file_selector(input_dir: str = "input") -> Optional[str]:
    """
    交互式文件选择器

    Args:
        input_dir: 输入文件夹路径

    Returns:
        Optional[str]: 选择的文件路径，如果用户取消则返回None
    """
    from core.pipeline.scanner import scan_input_files

    print("\n🚀 智能视频制作系统")
    print("正在扫描可处理的文件或文件夹...")

    # 扫描文件
    files = scan_input_files(input_dir)

    # 显示菜单
    display_file_menu(files)

    # 获取用户选择
    return get_user_file_selection(files)


def interactive_music_selector(project_root: str = None):
    """
    交互式背景音乐选择器

    Args:
        project_root: 项目根目录路径

    Returns:
        str: 选择的音乐文件名，或空字符串表示无音乐
        None: 用户取消操作（按q）
    """
    if project_root is None:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    music_dir = os.path.join(project_root, "music")

    if not os.path.exists(music_dir):
        print(f"⚠️ 未找到music文件夹: {music_dir}")
        return ""

    # 扫描音乐文件（支持常见音频格式）
    music_files = []
    supported_formats = ['.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg']

    for file in os.listdir(music_dir):
        if any(file.lower().endswith(ext) for ext in supported_formats):
            file_path = os.path.join(music_dir, file)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                music_files.append({
                    'name': file,
                    'path': file_path,
                    'size': file_size,
                    'size_mb': file_size / (1024 * 1024)
                })

    if not music_files:
        print("⚠️ music文件夹中未找到音乐文件")
        return ""

    # 按文件名排序
    music_files.sort(key=lambda x: x['name'])

    # 显示菜单
    print_section("请选择背景音乐", "🎵", "=")
    print(" 0. 无背景音乐")
    for i, music in enumerate(music_files, 1):
        print(f"{i:2}. {music['name']}")
        print(f"     大小: {music['size_mb']:.1f}MB")

    # 获取用户选择
    while True:
        try:
            print("=" * 60)
            choice = input(f"请选择背景音乐 (0-{len(music_files)}) 或输入 'q' 返回上一级: ").strip()

            if choice.lower() == 'q':
                return None  # 用户取消

            idx = int(choice)

            if idx == 0:
                print("✅ 您选择了: 无背景音乐")
                return ""  # 无音乐
            elif 1 <= idx <= len(music_files):
                selected = music_files[idx - 1]
                print(f"✅ 您选择了: {selected['name']}")
                return selected['name']  # 返回音乐文件名
            else:
                print(f"❌ 无效选择，请输入 0-{len(music_files)} 之间的数字")
        except ValueError:
            print("❌ 请输入有效的数字")
        except KeyboardInterrupt:
            print("\n👋 操作已取消")
            return None  # 用户取消


def print_section(title: str, icon: str = "📋", style: str = "-") -> None:
    """打印带格式的章节标题
    
    Args:
        title: 标题文本
        icon: 图标 (默认 📋)
        style: 分隔线样式，"-" 或 "=" (默认 "-")
    """
    separator = style * 60
    print(f"\n{separator}")
    print(f"{icon} {title}")
    print(separator)


def _prompt_split_mode() -> Optional[str]:
    """提示用户选择文本切分模式，返回 punctuation/manual/agent。"""
    choice = prompt_choice(
        "请选择文本切分方式",
        ["手动切分(根据换行符)", "按标点切分(中英文句号、问号、感叹号、分号)", "Agent智能分段并选择画面模式"],
        default_index=1,
    )
    if choice is None:
        return None
    if choice.startswith("手动"):
        return "manual"
    if choice.startswith("Agent"):
        return "agent"
    return "punctuation"


# ================================================================================
# CLI主要业务逻辑 (从 __main__.py 迁移)
# ================================================================================

def _interactive_skill_selector(project_root: str) -> Optional[str]:
    """交互式写作技能选择器"""
    import sys
    from core.config import config, Config
    
    skills_dir = os.path.join(project_root, "skills", "step1")
    if not os.path.exists(skills_dir):
        return "book-video-script"

    available_skills = [
        d for d in os.listdir(skills_dir)
        if os.path.isdir(os.path.join(skills_dir, d)) and not d.startswith(".")
    ]
    available_skills.sort()
    if not available_skills:
        return "book-video-script"

    default_skill = getattr(config, "STEP1_AGENT_SKILL", "book-video-script")
    if default_skill not in available_skills:
        default_skill = "book-video-script" if "book-video-script" in available_skills else available_skills[0]

    try:
        default_idx = available_skills.index(default_skill)
    except ValueError:
        default_idx = 0

    selected_skill = prompt_choice("请选择要使用的写作技能 (Skill)", available_skills, default_index=default_idx)
    if selected_skill is None:
        return None

    # 应用覆盖
    os.environ["STEP1_AGENT_SKILL"] = selected_skill
    setattr(config, "STEP1_AGENT_SKILL", selected_skill)
    setattr(Config, "STEP1_AGENT_SKILL", selected_skill)
    config_module = sys.modules.get("core.config")
    if config_module:
        setattr(config_module, "STEP1_AGENT_SKILL", selected_skill)
    print(f"✅ 已选择技能: {selected_skill}\n")
    return selected_skill


def _select_entry_and_context(project_root: str, output_dir: str):
    """交互式选择新建项目或打开现有项目"""
    while True:
        entry = prompt_choice("请选择操作", ["新建项目（从文档开始）", "打开现有项目（从output选择）"], default_index=0)
        if entry is None:
            return None
        if entry.startswith("新建项目"):
            input_file = interactive_file_selector(input_dir=os.path.join(project_root, "input"))
            if input_file is None:
                print("\n👋 返回上一级")
                continue
            
            selected_skill = _interactive_skill_selector(project_root)
            if selected_skill is None:
                print("\n👋 返回上一级")
                continue
                
            mode = prompt_choice("请选择处理方式", ["全自动（一次性全部生成）", "分步处理（每步确认并可修改产物）"], default_index=0)
            if mode is None:
                print("👋 返回上一级")
                continue
            run_mode = "auto" if mode.startswith("全自动") else "step"
            extra_requirements = _prompt_step1_extra_requirements()
            return {
                "entry": "new",
                "input_file": input_file,
                "run_mode": run_mode,
                "extra_requirements": extra_requirements,
            }

        project_dir = interactive_project_selector(output_dir=os.path.join(project_root, "output"))
        if not project_dir:
            print("👋 返回上一级")
            continue
            
        from core.pipeline.scanner import detect_project_progress
        
        # 检测项目进度并显示步骤选项
        progress = detect_project_progress(project_dir)
        
        # 显示完整进度状态并让用户选择要执行的步骤
        selected_step = display_project_progress_and_select_step(progress)
        if selected_step is None:
            project_dir = None
            continue
            
        step_val = selected_step
        
        return {"entry": "existing", "project_dir": project_dir, "selected_step": step_val}


def _prompt_step1_extra_requirements() -> str:
    """Prompt for optional Step 1 requirements inserted into the agent prompt."""
    print("\n请输入第一步额外要求（可选，直接回车跳过）")
    return input("额外要求: ").strip()


def _prompt_segment_generation_scope(
    project_output_dir: str,
    step_label: str,
    opening_label: str,
    allow_opening: bool = True,
) -> Optional[Dict[str, Any]]:
    """提示用户选择全量或部分生成段落资源"""
    resource_label = "画面素材" if step_label in {"图像", "画面"} else "音频"
    script_path = os.path.join(project_output_dir, 'text', 'script.json')
    script_data = load_json_file(script_path)
    segments = (script_data or {}).get('segments') or []
    total_segments = len(segments)

    if total_segments == 0:
        print(f"⚠️ 未找到脚本分段，默认执行全部{step_label}生成。")
        return {"mode": "full", "segments": [], "regenerate_opening": False, "total_segments": 0}

    print(f"当前脚本共 {total_segments} 个段落。")
    choice = prompt_choice(
        f"请选择{step_label}生成方式",
        ["全量生成（覆盖全部段落）", "部分生成（手动选择段落）"],
        default_index=0,
    )
    if choice is None:
        return None
    if choice.startswith("全量"):
        return {"mode": "full", "segments": [], "regenerate_opening": False, "total_segments": total_segments}

    if allow_opening:
        print(
            f"输入 0 可重新生成{opening_label}；输入 1-{total_segments} 选择段落，可用空格或逗号分隔多个数字。"
        )
        print(f"💡 提示：输入 N 可自动检测并补全缺失的{resource_label}。输入 q 返回上一级。")
    else:
        print(
            f"输入 1-{total_segments} 选择段落，可用空格或逗号分隔多个数字。"
        )
        print(f"💡 提示：输入 N 可自动检测并补全缺失的{resource_label}。输入 q 返回上一级。")

    while True:
        try:
            raw = input("请输入段落编号: ").strip()
        except KeyboardInterrupt:
            print("\n操作已取消")
            return None

        if raw.lower() == 'q':
            return None
        if not raw:
            print("❌ 未输入任何内容，请重新输入。")
            continue

        if raw.lower() == 'n':
            from core.infra.project_paths import ProjectPaths
            paths = ProjectPaths(project_output_dir)
            missing_indices = []
            missing_opening = False

            if allow_opening:
                if step_label in {"图像", "画面"}:
                    if not os.path.exists(paths.opening_image()):
                        missing_opening = True
                elif step_label == "语音":
                    if not os.path.exists(paths.opening_audio()):
                        missing_opening = True

            for i in range(1, total_segments + 1):
                if step_label in {"图像", "画面"}:
                    media_exists = False
                    for ext in ("png", "jpg", "jpeg", "mp4", "mov", "avi", "mkv", "webm", "flv", "m4v"):
                        if os.path.exists(os.path.join(paths.images, f"segment_{i}.{ext}")):
                            media_exists = True
                            break
                    if not media_exists:
                        missing_indices.append(i)
                elif step_label == "语音":
                    if not paths.segment_audio_exists(i):
                        missing_indices.append(i)

            if not missing_indices and not missing_opening:
                print(f"✅ 未检测到缺失的{resource_label}，请重新选择或输入 q 返回。")
                continue

            if missing_indices:
                seg_text = '、'.join(str(i) for i in missing_indices)
                print(f"✅ 自动检测到以下段落缺失并选择: 第 {seg_text} 段")
            if missing_opening:
                print(f"✅ 自动检测到{opening_label}缺失并将重新生成")
            
            return {
                "mode": "partial",
                "segments": missing_indices,
                "regenerate_opening": missing_opening,
                "total_segments": total_segments,
            }

        tokens = raw.replace('，', ' ').replace(',', ' ').split()
        regenerate_opening = False
        selected_indices: List[int] = []
        invalid_token: Optional[str] = None

        for token in tokens:
            if token == '0' and allow_opening:
                regenerate_opening = True
                continue
            try:
                idx = int(token)
            except ValueError:
                invalid_token = token
                break
            if idx < 1 or idx > total_segments:
                invalid_token = token
                break
            selected_indices.append(idx)

        if invalid_token is not None:
            if allow_opening:
                print(f"❌ 输入 {invalid_token} 超出范围，请输入 0 或 1-{total_segments} 的数字。")
            else:
                print(f"❌ 输入 {invalid_token} 超出范围，请输入 1-{total_segments} 的数字。")
            continue

        selected_indices = sorted(set(selected_indices))
        if selected_indices:
            seg_text = '、'.join(str(i) for i in selected_indices)
            print(f"✅ 已选择第 {seg_text} 段")
        if allow_opening and regenerate_opening:
            print(f"✅ 将重新生成{opening_label}")
        if not selected_indices and not (allow_opening and regenerate_opening):
            print("❌ 未选择任何段落，请重新输入。")
            continue

        return {
            "mode": "partial",
            "segments": selected_indices,
            "regenerate_opening": regenerate_opening if allow_opening else False,
            "total_segments": total_segments,
        }


def _run_specific_step(
    target_step, project_output_dir,
    llm_server_step1_5, llm_model_step1_5,
    llm_server_step2, llm_model_step2, llm_base_url_step2,
    llm_server_step4, llm_model_step4, llm_base_url_step4,
    image_server, image_model, image_size, video_size, image_style_preset,
    tts_server, voice, tts_model, speech_rate, loudness_rate, emotion, emotion_scale, num_segments,
    enable_subtitles, bgm_filename,
    cover_image_size, cover_image_server, cover_image_model, cover_image_style, cover_image_count, opening_quote=True,
    mute_cut_threshold=400, mute_cut_min_silence_ms=200, mute_cut_remain_ms=100,
    visual_mode="static_image", motion_style_preset="data_driven",
    motion_max_turns=60, motion_render_fps=30, motion_concurrency=1,
    image_prompt_template="keywords",
):
    """执行指定步骤并返回结果"""
    from core.pipeline.steps import run_step_1, run_step_1_5, run_step_2, run_step_3, run_step_4, run_step_5, run_step_6
    
    print(f"\n正在执行步骤 {target_step}...")
    
    if target_step == 1:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        input_file = interactive_file_selector(input_dir=os.path.join(project_root, "input"))
        if input_file is None:
            return {"success": False, "message": "用户取消", "cancelled": True}
        selected_skill = _interactive_skill_selector(project_root)
        if selected_skill is None:
            return {"success": False, "message": "用户取消", "cancelled": True}
        extra_requirements = _prompt_step1_extra_requirements()

        from core.pipeline.scanner import clear_downstream_outputs

        print("🎬 正在重新生成第一步内容...")
        result = run_step_1(
            input_file,
            os.path.dirname(project_output_dir),
            num_segments,
            extra_requirements=extra_requirements,
            project_output_dir=project_output_dir,
        )
        if result.get("success"):
            clear_downstream_outputs(project_output_dir, from_step=1)
            result["message"] = "步骤1重新生成完成"
    elif target_step == 1.5:
        split_mode = _prompt_split_mode()
        if split_mode is None:
            return {"success": False, "message": "用户取消", "cancelled": True}
        result = run_step_1_5(
            project_output_dir,
            num_segments,
            split_mode=split_mode,
            llm_server_step1_5=llm_server_step1_5,
            llm_model_step1_5=llm_model_step1_5,
        )
    elif target_step == 2:
        result = run_step_2(
            llm_server_step2,
            llm_model_step2,
            llm_base_url_step2,
            project_output_dir,
        )
    elif target_step == 3:
        selection = _prompt_segment_generation_scope(
            project_output_dir,
            step_label="语音",
            opening_label="开场金句音频",
            allow_opening=opening_quote,
        )
        if selection is None:
            return {"success": False, "message": "用户取消", "cancelled": True}
        if selection["mode"] == "partial":
            result = run_step_3(
                tts_server,
                voice,
                tts_model,
                project_output_dir,
                opening_quote,
                target_segments=selection["segments"],
                regenerate_opening=selection.get("regenerate_opening", False),
                speech_rate=speech_rate,
                loudness_rate=loudness_rate,
                emotion=emotion,
                emotion_scale=emotion_scale,
                mute_cut_threshold=mute_cut_threshold,
                mute_cut_min_silence_ms=mute_cut_min_silence_ms,
                mute_cut_remain_ms=mute_cut_remain_ms,
            )
        else:
            result = run_step_3(
                tts_server,
                voice,
                tts_model,
                project_output_dir,
                opening_quote,
                speech_rate=speech_rate,
                loudness_rate=loudness_rate,
                emotion=emotion,
                emotion_scale=emotion_scale,
                mute_cut_threshold=mute_cut_threshold,
                mute_cut_min_silence_ms=mute_cut_min_silence_ms,
                mute_cut_remain_ms=mute_cut_remain_ms,
            )
    elif target_step == 4:
        selected_visual_mode = prompt_visual_mode_choice(visual_mode)
        if selected_visual_mode is None:
            return {"success": False, "message": "用户取消", "cancelled": True}

        selected_style = image_style_preset
        selected_motion_style = motion_style_preset
        if selected_visual_mode in {"static_image", "mixed"}:
            selected_style = prompt_image_style_choice(style_type="segment")
            if selected_style is None:
                return {"success": False, "message": "用户取消", "cancelled": True}
        if selected_visual_mode in {"motion_agent", "mixed"}:
            selected_motion_style = prompt_motion_style_choice(motion_style_preset)
            if selected_motion_style is None:
                return {"success": False, "message": "用户取消", "cancelled": True}

        selection = _prompt_segment_generation_scope(
            project_output_dir,
            step_label="画面",
            opening_label="开场视频",
            allow_opening=opening_quote,
        )
        if selection is None:
            return {"success": False, "message": "用户取消", "cancelled": True}
        if selection["mode"] == "partial":
            result = run_step_4(
                image_server,
                image_model,
                image_size,
                selected_style,
                project_output_dir,
                opening_quote,
                target_segments=selection["segments"],
                regenerate_opening=selection.get("regenerate_opening", False),
                llm_model=llm_model_step4,
                llm_server=llm_server_step4,
                llm_base_url=llm_base_url_step4,
                visual_mode=selected_visual_mode,
                motion_style_preset=selected_motion_style,
                motion_max_turns=motion_max_turns,
                motion_render_fps=motion_render_fps,
                motion_concurrency=motion_concurrency,
                image_prompt_template=image_prompt_template,
            )
        else:
            result = run_step_4(
                image_server,
                image_model,
                image_size,
                selected_style,
                project_output_dir,
                opening_quote,
                llm_model=llm_model_step4,
                llm_server=llm_server_step4,
                llm_base_url=llm_base_url_step4,
                visual_mode=selected_visual_mode,
                motion_style_preset=selected_motion_style,
                motion_max_turns=motion_max_turns,
                motion_render_fps=motion_render_fps,
                motion_concurrency=motion_concurrency,
                image_prompt_template=image_prompt_template,
            )
    elif target_step == 5:
        # 让用户选择背景音乐
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        selected_bgm = interactive_music_selector(project_root)

        # 如果用户取消（返回None），则取消步骤5的执行
        if selected_bgm is None:
            return {"success": False, "message": "用户取消", "cancelled": True}

        # selected_bgm为空字符串表示无音乐，否则为音乐文件名
        # 将空字符串转换为None以保持与原有逻辑兼容
        selected_bgm_filename = selected_bgm if selected_bgm else None

        # 第五步允许与生图尺寸解耦，优先使用 video_size
        result = run_step_5(
            project_output_dir,
            video_size or image_size,
            enable_subtitles,
            selected_bgm_filename,  # 使用用户选择的音乐
            voice,
            tts_model,
            opening_quote,
            speech_rate=speech_rate,
            loudness_rate=loudness_rate,
            emotion=emotion,
            emotion_scale=emotion_scale,
            mute_cut_threshold=mute_cut_threshold,
            mute_cut_min_silence_ms=mute_cut_min_silence_ms,
            mute_cut_remain_ms=mute_cut_remain_ms,
        )
    elif target_step == 6:
        # 让用户选择封面图片风格
        selected_style = prompt_image_style_choice(style_type="cover")
        if selected_style is None:
            return {"success": False, "message": "用户取消", "cancelled": True}

        # 封面尺寸选择交互：默认一次生成配置的全部尺寸，也可只选一个
        from core.config import COVER_IMAGE_SIZE_KEYS, COVER_IMAGE_SIZE_PRESETS

        configured = [key for key in COVER_IMAGE_SIZE_KEYS or [] if key in COVER_IMAGE_SIZE_PRESETS]
        size_options = [f"{ratio} ({size})" for ratio, size in COVER_IMAGE_SIZE_PRESETS.items()]
        default_idx = 0
        if len(configured) > 1:
            all_option = "配置的全部尺寸：" + " + ".join(configured)
            size_options.insert(0, all_option)
        elif configured:
            default_idx = list(COVER_IMAGE_SIZE_PRESETS).index(configured[0])

        # 让用户选择尺寸
        print("\n请选择封面尺寸：")
        selected = prompt_choice("封面尺寸", size_options, default_index=default_idx)

        if selected is None:
            return {"success": False, "cancelled": True}

        # 解析选择的尺寸比例（从"16:9 (3200x1800)"提取"16:9"），pipeline会自动解析比例key
        selected_sizes = configured if len(configured) > 1 and selected == size_options[0] else selected.split(" ")[0]

        result = run_step_6(
            project_output_dir,
            selected_sizes,
            cover_image_server,
            cover_image_model,
            selected_style,
            cover_image_count,
        )
    else:
        result = {"success": False, "message": "无效的步骤"}
    
    return result


def _run_step_by_step_loop(
    project_output_dir, initial_step,
    llm_server_step1_5, llm_model_step1_5,
    llm_server_step2, llm_model_step2, llm_base_url_step2,
    llm_server_step4, llm_model_step4, llm_base_url_step4,
    image_server, image_model, image_size, video_size, image_style_preset,
    tts_server, voice, tts_model, speech_rate, loudness_rate, emotion, emotion_scale, num_segments,
    enable_subtitles, bgm_filename,
    cover_image_size, cover_image_server, cover_image_model, cover_image_style, cover_image_count, opening_quote=True,
    mute_cut_threshold=400, mute_cut_min_silence_ms=200, mute_cut_remain_ms=100,
    visual_mode="static_image", motion_style_preset="data_driven",
    motion_max_turns=60, motion_render_fps=30, motion_concurrency=1,
    image_prompt_template="keywords",
):
    """执行指定步骤，然后进入交互模式让用户选择下一步操作"""
    from core.pipeline.scanner import detect_project_progress
    
    # 首先执行指定的步骤
    if initial_step > 0:
        result = _run_specific_step(
            initial_step, project_output_dir,
            llm_server_step1_5, llm_model_step1_5,
            llm_server_step2, llm_model_step2, llm_base_url_step2,
            llm_server_step4, llm_model_step4, llm_base_url_step4,
            image_server, image_model, image_size, video_size, image_style_preset,
            tts_server, voice, tts_model, speech_rate, loudness_rate, emotion, emotion_scale, num_segments,
            enable_subtitles, bgm_filename,
            cover_image_size, cover_image_server, cover_image_model, cover_image_style, cover_image_count, opening_quote,
            mute_cut_threshold, mute_cut_min_silence_ms, mute_cut_remain_ms,
            visual_mode, motion_style_preset,
            motion_max_turns, motion_render_fps, motion_concurrency,
            image_prompt_template
        )
        
        # 显示执行结果
        if result.get("success"):
            print(f"✅ 步骤 {initial_step} 执行成功")
            msg = result.get("message")
            if isinstance(msg, str) and msg.strip():
                print(msg)
        else:
            if result.get("cancelled"):
                print("👋 已取消当前步骤")
                # 用户取消：不退出，继续进入交互循环让用户重新选择
            else:
                print(f"❌ 步骤 {initial_step} 执行失败: {result.get('message', '未知错误')}")
                return result  # 只有真正失败时才返回
    
    # 进入交互循环
    while True:
        # 重新检测项目进度
        progress = detect_project_progress(project_output_dir)
        current_step = progress.get('current_step', 0)
        
        print(f"\n📍 当前进度：已完成到第{current_step}步")
        print("💡 如需修改生成的内容，可编辑对应文件后再继续")
        
        # 让用户选择下一步操作
        selected_step = display_project_progress_and_select_step(progress)
        if selected_step is None:
            return {"success": True, "message": "用户退出"}
        
        # 执行选择的步骤
        result = _run_specific_step(
            selected_step, project_output_dir,
            llm_server_step1_5, llm_model_step1_5,
            llm_server_step2, llm_model_step2, llm_base_url_step2,
            llm_server_step4, llm_model_step4, llm_base_url_step4,
            image_server, image_model, image_size, video_size, image_style_preset,
            tts_server, voice, tts_model, speech_rate, loudness_rate, emotion, emotion_scale, num_segments,
            enable_subtitles, bgm_filename,
            cover_image_size, cover_image_server, cover_image_model, cover_image_style, cover_image_count, opening_quote,
            mute_cut_threshold, mute_cut_min_silence_ms, mute_cut_remain_ms,
            visual_mode, motion_style_preset,
            motion_max_turns, motion_render_fps, motion_concurrency,
            image_prompt_template
        )
        
        # 显示结果
        if result.get("success"):
            print(f"✅ 步骤 {selected_step} 执行成功")
            msg = result.get("message")
            if isinstance(msg, str) and msg.strip():
                print(msg)
            if selected_step == 5:
                print("\n🎉 视频制作完成！")
                if result.get("final_video"):
                    print(f"最终视频: {result.get('final_video')}")
        else:
            if result.get("cancelled"):
                print("👋 已取消当前步骤")
                continue
            print(f"❌ 步骤 {selected_step} 执行失败: {result.get('message', '未知错误')}")


def run_cli_main(
    input_file=None,
    num_segments: int = _UNSET,
    step1_5_split_mode: str = _UNSET,
    llm_server_step1_5: str = _UNSET,
    llm_model_step1_5: str = _UNSET,
    image_size: Optional[str] = _UNSET,
    video_size: Optional[str] = _UNSET,
    llm_server_step2: str = _UNSET,
    llm_model_step2: str = _UNSET,
    llm_base_url_step2: str = _UNSET,
    llm_server_step4: str = _UNSET,
    llm_model_step4: str = _UNSET,
    llm_base_url_step4: str = _UNSET,
    image_server: str = _UNSET,
    image_model: str = _UNSET,
    voice: Optional[str] = _UNSET,
    resource_id: Optional[str] = _UNSET,
    tts_model: Optional[str] = _UNSET,
    tts_emotion: Optional[str] = _UNSET,
    tts_emotion_scale: Optional[int] = _UNSET,
    tts_speech_rate: Optional[int] = _UNSET,
    tts_loudness_rate: Optional[int] = _UNSET,
    mute_cut_threshold: Optional[int] = _UNSET,
    mute_cut_min_silence_ms: Optional[int] = _UNSET,
    mute_cut_remain_ms: Optional[int] = _UNSET,
    output_dir: Optional[str] = None,
    visual_mode: str = _UNSET,
    motion_style_preset: str = _UNSET,
    motion_max_turns: Optional[int] = _UNSET,
    motion_render_fps: Optional[int] = _UNSET,
    motion_concurrency: Optional[int] = _UNSET,
    image_style_preset: str = _UNSET,
    image_prompt_template: str = _UNSET,
    enable_subtitles: bool = _UNSET,
    bgm_filename: Optional[str] = _UNSET,
    cover_image_size: Optional[str] = _UNSET,
    cover_image_server: Optional[str] = _UNSET,
    cover_image_model: Optional[str] = _UNSET,
    cover_image_style: str = _UNSET,
    cover_image_count: Optional[int] = _UNSET,
    run_mode: str = "auto",
    opening_quote: bool = _UNSET,
    extra_requirements: str = _UNSET,
) -> Dict[str, Any]:
    """CLI主要业务逻辑入口"""
    
    # 安全导入，避免循环导入
    try:
        # 设置项目路径
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
        from core.config import config, get_generation_params
        from core.pipeline.run_auto import run_auto
        from core.pipeline.steps import run_step_1
        
        params = get_generation_params()
        overrides = {
            "num_segments": num_segments,
            "step1_5_split_mode": step1_5_split_mode,
            "llm_server_step1_5": llm_server_step1_5,
            "llm_model_step1_5": llm_model_step1_5,
            "image_size": image_size,
            "video_size": video_size,
            "llm_server_step2": llm_server_step2,
            "llm_model_step2": llm_model_step2,
            "llm_base_url_step2": llm_base_url_step2,
            "llm_server_step4": llm_server_step4,
            "llm_model_step4": llm_model_step4,
            "llm_base_url_step4": llm_base_url_step4,
            "image_server": image_server,
            "image_model": image_model,
            "voice": voice,
            "resource_id": resource_id,
            "tts_model": tts_model,
            "tts_emotion": tts_emotion,
            "tts_emotion_scale": tts_emotion_scale,
            "tts_speech_rate": tts_speech_rate,
            "tts_loudness_rate": tts_loudness_rate,
            "mute_cut_threshold": mute_cut_threshold,
            "mute_cut_min_silence_ms": mute_cut_min_silence_ms,
            "mute_cut_remain_ms": mute_cut_remain_ms,
            "visual_mode": visual_mode,
            "motion_style_preset": motion_style_preset,
            "motion_max_turns": motion_max_turns,
            "motion_render_fps": motion_render_fps,
            "motion_concurrency": motion_concurrency,
            "image_style_preset": image_style_preset,
            "image_prompt_template": image_prompt_template,
            "enable_subtitles": enable_subtitles,
            "bgm_filename": bgm_filename,
            "cover_image_size": cover_image_size,
            "cover_image_server": cover_image_server,
            "cover_image_model": cover_image_model,
            "cover_image_style": cover_image_style,
            "cover_image_count": cover_image_count,
            "opening_quote": opening_quote,
            "extra_requirements": extra_requirements,
        }
        for key, value in overrides.items():
            if value is not _UNSET:
                params[key] = value

        num_segments = params["num_segments"]
        step1_5_split_mode = params.get("step1_5_split_mode", "punctuation")
        llm_server_step1_5 = params["llm_server_step1_5"]
        llm_model_step1_5 = params["llm_model_step1_5"]
        image_size = params["image_size"]
        video_size = params.get("video_size")
        llm_server_step2 = params["llm_server_step2"]
        llm_model_step2 = params["llm_model_step2"]
        llm_base_url_step2 = params["llm_base_url_step2"]
        llm_server_step4 = params["llm_server_step4"]
        llm_model_step4 = params["llm_model_step4"]
        llm_base_url_step4 = params["llm_base_url_step4"]
        image_server = params["image_server"]
        image_model = params["image_model"]
        voice = params["voice"]
        resource_id = params.get("resource_id", "seed-icl-2.0")
        tts_model = params.get("tts_model", getattr(config, "TTS_MODEL", ""))
        emotion = params["tts_emotion"]
        emotion_scale = params["tts_emotion_scale"]
        speech_rate = params["tts_speech_rate"]
        loudness_rate = params["tts_loudness_rate"]
        mute_cut_threshold = params["mute_cut_threshold"]
        mute_cut_min_silence_ms = params["mute_cut_min_silence_ms"]
        mute_cut_remain_ms = params["mute_cut_remain_ms"]
        try:
            emotion_scale = int(emotion_scale)
        except Exception:
            emotion_scale = 4
        try:
            speech_rate = int(speech_rate)
        except Exception:
            speech_rate = 0
        try:
            loudness_rate = int(loudness_rate)
        except Exception:
            loudness_rate = 0
        visual_mode = params.get("visual_mode", "static_image")
        motion_style_preset = params.get("motion_style_preset", "data_driven")
        try:
            motion_max_turns = int(params.get("motion_max_turns", 60))
        except Exception:
            motion_max_turns = 60
        try:
            motion_render_fps = int(params.get("motion_render_fps", 30))
        except Exception:
            motion_render_fps = 30
        try:
            motion_concurrency = int(params.get("motion_concurrency", 1))
        except Exception:
            motion_concurrency = 1
        image_style_preset = params["image_style_preset"]
        image_prompt_template = params["image_prompt_template"]
        enable_subtitles = params["enable_subtitles"]
        bgm_filename = params["bgm_filename"]
        opening_quote = params["opening_quote"]
        cover_image_size = params.get("cover_image_size", image_size)
        cover_image_server = params["cover_image_server"]
        cover_image_model = params.get("cover_image_model", image_model)
        cover_image_style = params.get("cover_image_style", "cover01")
        try:
            cover_image_count = int(params.get("cover_image_count", 1))
        except Exception:
            cover_image_count = 1
        if cover_image_count < 1:
            cover_image_count = 1

        image_size = image_size or config.DEFAULT_IMAGE_SIZE
        video_size = video_size or params.get("image_size") or config.DEFAULT_IMAGE_SIZE
        voice = voice or config.DEFAULT_VOICE
        output_dir = output_dir or config.DEFAULT_OUTPUT_DIR
        
    except ImportError as e:
        return {"success": False, "message": f"导入失败: {e}"}

    if not os.path.isabs(output_dir):
        output_dir = os.path.join(project_root, output_dir)

    # 验证参数
    tts_server = "bytedance"  # 目前只支持bytedance TTS
    try:
        config.validate_parameters(
            num_segments, llm_server_step2, image_server,
            tts_server, image_model, image_size, llm_model=llm_model_step2,
            image_prompt_template=image_prompt_template,
        )
        config.validate_model_provider_pair("image", cover_image_server, cover_image_model)
    except Exception:
        # 兼容旧入口：模型与服务商不匹配时自动推断服务商，再次校验
        try:
            from core.startup import validate_startup_args

            llm_server_step2, _, _ = validate_startup_args(
                num_segments=num_segments,
                image_size=image_size,
                llm_model=llm_model_step2,
                image_model=image_model,
                voice=voice,
            )
            cover_image_server = image_server

            config.validate_parameters(
                num_segments, llm_server_step2, image_server,
                tts_server, image_model, image_size, llm_model=llm_model_step2,
                image_prompt_template=image_prompt_template,
            )
            config.validate_model_provider_pair("image", cover_image_server, cover_image_model)
        except Exception as e:
            return {"success": False, "message": f"参数验证失败: {e}"}

    selection = None
    if input_file is None:
        selection = _select_entry_and_context(project_root, output_dir)
        if selection is None:
            return {"success": False, "message": "用户取消", "execution_time": 0, "error": "用户取消"}
        if selection["entry"] == "new":
            input_file = selection["input_file"]
            run_mode = selection["run_mode"]
            params["extra_requirements"] = selection.get("extra_requirements", "")
        else:
            # 处理已有项目的步骤执行循环
            project_output_dir = selection["project_dir"]
            return _run_step_by_step_loop(
                project_output_dir, selection["selected_step"],
                llm_server_step1_5, llm_model_step1_5,
                llm_server_step2, llm_model_step2, llm_base_url_step2,
                llm_server_step4, llm_model_step4, llm_base_url_step4,
                image_server, image_model, image_size, video_size, image_style_preset,
                tts_server, voice, tts_model, speech_rate, loudness_rate,
                emotion, emotion_scale, num_segments,
                enable_subtitles, bgm_filename, cover_image_size, cover_image_server, cover_image_model,
                cover_image_style, cover_image_count, opening_quote,
                mute_cut_threshold, mute_cut_min_silence_ms, mute_cut_remain_ms,
                visual_mode, motion_style_preset,
                motion_max_turns, motion_render_fps, motion_concurrency,
                image_prompt_template
            )

    if input_file is not None and not os.path.isabs(input_file):
        input_file = os.path.join(project_root, input_file)

    if run_mode == "auto":
        from core.config import VideoGenerationConfig

        gen_config = VideoGenerationConfig.from_cli_params(
            params,
            input_file=input_file,
            output_dir=output_dir,
            tts_server=tts_server,
            cover_image_size=cover_image_size,
            speech_rate=speech_rate,
            loudness_rate=loudness_rate,
            emotion=emotion,
            emotion_scale=emotion_scale,
        )

        result = run_auto(gen_config)
        if result.get("success"):
            print_section("全自动模式完成", "🎬", "=")
            print(f"最终视频: {result.get('final_video')}")
            if result.get('cover_images'):
                print(f"封面图片: {len(result.get('cover_images'))} 张")
        else:
            print(f"\n❌ 处理失败: {result.get('message')}")
        return result
    else:  # step mode
        # 先执行步骤1创建项目
        result = run_step_1(
            input_file,
            output_dir,
            num_segments,
            extra_requirements=params.get("extra_requirements", ""),
        )
        if not result.get("success"):
            print(f"\n❌ 步骤1失败: {result.get('message')}")
            return result
        
        print("✅ 步骤1执行成功")
        project_output_dir = result.get("project_output_dir")
        
        # 步骤1完成后，进入分步处理循环
        return _run_step_by_step_loop(
            project_output_dir, 0,  # 不执行初始步骤，直接进入交互模式
            llm_server_step1_5, llm_model_step1_5,
            llm_server_step2, llm_model_step2, llm_base_url_step2,
            llm_server_step4, llm_model_step4, llm_base_url_step4,
            image_server, image_model, image_size, video_size, image_style_preset,
            tts_server, voice, tts_model, speech_rate, loudness_rate,
            emotion, emotion_scale, num_segments,
            enable_subtitles, bgm_filename, cover_image_size, cover_image_server, cover_image_model,
            cover_image_style, cover_image_count, opening_quote,
            mute_cut_threshold, mute_cut_min_silence_ms, mute_cut_remain_ms,
            visual_mode, motion_style_preset,
            motion_max_turns, motion_render_fps, motion_concurrency,
            image_prompt_template
        )
