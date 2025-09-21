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
    from core.project_scanner import scan_output_projects
    
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
    # 步骤定义
    steps = [
        (1, "内容生成", progress.get('has_raw', False)),
        (1.5, "脚本分段", progress.get('has_script', False)),
        (2, "要点提取", progress.get('has_keywords', False)),
        (3, "图像生成", progress.get('images_ok', False)),
        (4, "语音合成", progress.get('audio_ok', False)),
        (5, "视频合成", progress.get('has_final_video', False))
    ]
    
    current_step = progress.get('current_step', 0)
    
    print(f"\n📊 项目进度状态")
    print("=" * 60)
    
    # 显示步骤状态
    for step_num, step_name, is_completed in steps:
        if is_completed:
            status = "✅ 已完成"
        elif step_num <= current_step:
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
    if progress.get('has_script', False):
        allowed_steps.append(1.5)  # 允许重做脚本分段
    if progress.get('has_keywords', False):
        allowed_steps.append(2)    # 允许重做要点提取
    if progress.get('images_ok', False):
        allowed_steps.append(3)    # 允许重做图像生成
    if progress.get('audio_ok', False):
        allowed_steps.append(4)    # 允许重做语音合成
    if progress.get('has_final_video', False):
        allowed_steps.append(5)    # 允许重做视频合成

    # 添加可执行的下一步
    if not progress.get('has_script', False) and progress.get('has_raw', False):
        allowed_steps.append(1.5)  # 可执行脚本分段
    if not progress.get('has_keywords', False) and progress.get('has_script', False):
        allowed_steps.append(2)    # 可执行要点提取
    if not progress.get('images_ok', False) and progress.get('has_keywords', False):
        allowed_steps.append(3)    # 可执行图像生成
    if not progress.get('audio_ok', False) and progress.get('has_script', False):
        allowed_steps.append(4)    # 可执行语音合成（只需script.json）
    if not progress.get('has_final_video', False) and progress.get('images_ok', False) and progress.get('audio_ok', False):
        allowed_steps.append(5)    # 可执行视频合成（需要图像和音频都完成）
    
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


def display_file_menu(files: List[Dict[str, Any]]) -> None:
    """
    显示文件选择菜单
    
    Args:
        files: 文件信息列表
    """
    print_section("发现以下可处理的文件", "📚", "=")
    
    if not files:
        print("❌ 在input文件夹中未找到PDF、EPUB或MOBI文件")
        print("请将要处理的PDF、EPUB或MOBI文件放入input文件夹中")
        return
    
    for i, file_info in enumerate(files, 1):
        if file_info['extension'] == '.epub':
            file_type = "📖 EPUB"
        elif file_info['extension'] == '.pdf':
            file_type = "📄 PDF"
        elif file_info['extension'] == '.mobi':
            file_type = "📱 MOBI"
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
            choice = input(f"请选择要处理的文件 (1-{len(files)}) 或输入 'q' 返回上一级: ").strip()
            
            if choice.lower() == 'q':
                print("👋 返回上一级")
                return None
            
            file_index = int(choice) - 1
            
            if 0 <= file_index < len(files):
                selected_file = files[file_index]
                print(f"\n✅ 您选择了: {selected_file['name']}")
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
    from core.project_scanner import scan_input_files
    
    print("\n🚀 智能视频制作系统")
    print("正在扫描可处理的文件...")
    
    # 扫描文件
    files = scan_input_files(input_dir)
    
    # 显示菜单
    display_file_menu(files)
    
    # 获取用户选择
    return get_user_file_selection(files)


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


# ================================================================================
# CLI主要业务逻辑 (从 __main__.py 迁移)
# ================================================================================

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
            mode = prompt_choice("请选择处理方式", ["全自动（一次性全部生成）", "分步处理（每步确认并可修改产物）"], default_index=0)
            if mode is None:
                print("👋 返回上一级")
                continue
            run_mode = "auto" if mode.startswith("全自动") else "step"
            return {"entry": "new", "input_file": input_file, "run_mode": run_mode}

        project_dir = interactive_project_selector(output_dir=os.path.join(project_root, "output"))
        if not project_dir:
            print("👋 返回上一级")
            continue
        from core.project_scanner import detect_project_progress
        
        # 检测项目进度并显示步骤选项
        progress = detect_project_progress(project_dir)
        
        # 显示完整进度状态并让用户选择要执行的步骤
        selected_step = display_project_progress_and_select_step(progress)
        if selected_step is None:
            project_dir = None
            continue
            
        step_val = selected_step
        
        return {"entry": "existing", "project_dir": project_dir, "selected_step": step_val}


def _run_specific_step(
    target_step, project_output_dir, llm_server, llm_model, image_server, image_model,
    image_size, image_style_preset, opening_image_style, tts_server, voice,
    num_segments, enable_subtitles, bgm_filename, opening_quote=True
):
    """执行指定步骤并返回结果"""
    from core.pipeline import run_step_1_5, run_step_2, run_step_3, run_step_4, run_step_5
    
    print(f"\n正在执行步骤 {target_step}...")
    
    if target_step == 1.5:
        result = run_step_1_5(project_output_dir, num_segments)
    elif target_step == 2:
        result = run_step_2(llm_server, llm_model, project_output_dir)
    elif target_step == 3:
        result = run_step_3(image_server, image_model, image_size, image_style_preset, project_output_dir, opening_image_style, opening_quote)
    elif target_step == 4:
        result = run_step_4(tts_server, voice, project_output_dir, opening_quote)
    elif target_step == 5:
        result = run_step_5(project_output_dir, image_size, enable_subtitles, bgm_filename, voice, opening_quote)
    else:
        result = {"success": False, "message": "无效的步骤"}
    
    return result


def _run_step_by_step_loop(
    project_output_dir, initial_step, llm_server, llm_model, image_server, image_model,
    image_size, image_style_preset, opening_image_style, tts_server, voice,
    num_segments, enable_subtitles, bgm_filename, opening_quote=True
):
    """执行指定步骤，然后进入交互模式让用户选择下一步操作"""
    from core.project_scanner import detect_project_progress
    
    # 首先执行指定的步骤
    if initial_step > 0:
        result = _run_specific_step(
            initial_step, project_output_dir, llm_server, llm_model, image_server, image_model,
            image_size, image_style_preset, opening_image_style, tts_server, voice,
            num_segments, enable_subtitles, bgm_filename, opening_quote
        )
        
        # 显示执行结果
        if result.get("success"):
            print(f"✅ 步骤 {initial_step} 执行成功")
        else:
            print(f"❌ 步骤 {initial_step} 执行失败: {result.get('message', '未知错误')}")
            return result
    
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
            selected_step, project_output_dir, llm_server, llm_model, image_server, image_model,
            image_size, image_style_preset, opening_image_style, tts_server, voice,
            num_segments, enable_subtitles, bgm_filename, opening_quote
        )
        
        # 显示结果
        if result.get("success"):
            print(f"✅ 步骤 {selected_step} 执行成功")
            if selected_step == 5:
                print(f"\n🎉 视频制作完成！")
                if result.get("final_video"):
                    print(f"最终视频: {result.get('final_video')}")
        else:
            print(f"❌ 步骤 {selected_step} 执行失败: {result.get('message', '未知错误')}")


def run_cli_main(
    input_file=None,
    target_length: int = 1000,
    num_segments: int = 10,
    image_size: str = None,
    llm_model: str = "google/gemini-2.5-pro",
    image_model: str = "doubao-seedream-3-0-t2i-250415",
    voice: str = None,
    output_dir: str = None,
    image_style_preset: str = "style05",
    opening_image_style: str = "des01",
    enable_subtitles: bool = True,
    bgm_filename: str = None,
    run_mode: str = "auto",
    opening_quote: bool = True,
) -> Dict[str, Any]:
    """CLI主要业务逻辑入口"""
    
    # 安全导入，避免循环导入
    try:
        # 设置项目路径
        project_root = os.path.dirname(os.path.dirname(__file__))
            
        from config import config
        from core.validators import validate_startup_args
        from core.pipeline import run_auto, run_step_1
        
        # 使用配置默认值填充None参数
        image_size = image_size or config.DEFAULT_IMAGE_SIZE
        voice = voice or config.DEFAULT_VOICE
        output_dir = output_dir or config.DEFAULT_OUTPUT_DIR
        
    except ImportError as e:
        return {"success": False, "message": f"导入失败: {e}"}

    if not os.path.isabs(output_dir):
        output_dir = os.path.join(project_root, output_dir)

    # 验证参数
    try:
        llm_server, image_server, tts_server = validate_startup_args(
            target_length, num_segments, image_size, llm_model, image_model, voice
        )
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
        else:
            # 处理已有项目的步骤执行循环
            project_output_dir = selection["project_dir"]
            return _run_step_by_step_loop(
                project_output_dir, selection["selected_step"],
                llm_server, llm_model, image_server, image_model, image_size, image_style_preset,
                opening_image_style, tts_server, voice, num_segments,
                enable_subtitles, bgm_filename, opening_quote
            )

    if input_file is not None and not os.path.isabs(input_file):
        input_file = os.path.join(project_root, input_file)

    if run_mode == "auto":
        result = run_auto(
            input_file, output_dir, target_length, num_segments, image_size,
            llm_server, llm_model, image_server, image_model, tts_server, voice,
            image_style_preset, opening_image_style, enable_subtitles, bgm_filename,
            opening_quote,
        )
        if result.get("success"):
            print_section("步骤 5/5 完成：视频合成", "🎬", "=")
            print(f"最终视频: {result.get('final_video')}")
        else:
            print(f"\n❌ 处理失败: {result.get('message')}")
        return result
    else:  # step mode
        # 先执行步骤1创建项目
        result = run_step_1(input_file, output_dir, llm_server, llm_model, target_length, num_segments)
        if not result.get("success"):
            print(f"\n❌ 步骤1失败: {result.get('message')}")
            return result
        
        print("✅ 步骤1执行成功")
        project_output_dir = result.get("project_output_dir")
        
        # 步骤1完成后，进入分步处理循环
        from core.project_scanner import detect_project_progress
        
        progress = detect_project_progress(project_output_dir)
        current_step = progress.get('current_step', 1)
        
        print(f"\n📍 当前进度：已完成到第{current_step}步")
        print("💡 如需修改生成的内容，可编辑对应文件后再继续")
        
        return _run_step_by_step_loop(
            project_output_dir, 0,  # 不执行初始步骤，直接进入交互模式
            llm_server, llm_model, image_server, image_model, image_size, image_style_preset,
            opening_image_style, tts_server, voice, num_segments,
            enable_subtitles, bgm_filename, opening_quote
        )
