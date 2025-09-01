"""
CLI界面特定的交互函数
这些函数只用于命令行界面的用户交互

调用关系:
- cli/__main__.py: 调用交互式文件选择器、项目选择器、步骤选择等用户界面函数
- 调用core/project_scanner.py进行文件和项目扫描
- 专门为CLI界面提供用户交互功能，包括菜单显示、用户输入处理等
- 从utils.py迁移而来的UI相关函数，保持CLI界面的简洁和用户友好
"""

import os
from typing import Dict, Any, List, Optional


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
    
    # 确定允许的步骤：不允许第1步，允许当前步骤重做和下一步执行
    allowed_steps = []
    if current_step >= 1.5:
        allowed_steps.append(1.5)  # 允许重做脚本分段
    if current_step >= 2:
        allowed_steps.append(2)    # 允许重做要点提取
    if current_step >= 3:
        allowed_steps.append(3)    # 允许重做图像生成
    if current_step >= 4:
        allowed_steps.append(4)    # 允许重做语音合成
    if current_step >= 5:
        allowed_steps.append(5)    # 允许重做视频合成
    
    # 添加下一步（如果存在）
    if current_step < 5:
        next_steps = {1: 1.5, 1.5: 2, 2: 3, 3: 4, 4: 5}
        next_step = next_steps.get(current_step)
        if next_step and next_step not in allowed_steps:
            allowed_steps.append(next_step)
    
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


def prompt_step_action(current_step) -> Optional[str]:
    """
    分步处理模式的简化选择：继续下一步、重新生成、退出
    返回 "next", "redo", None
    """
    # 定义步骤名称
    step_names = {1: "内容生成", 1.5: "脚本分段", 2: "要点提取", 3: "图像生成", 4: "语音合成", 5: "视频合成"}
    current_name = step_names.get(current_step, f"步骤{current_step}")
    
    # 如果所有步骤已完成
    if current_step >= 5:
        options = [f"重做--{current_name}", "退出"]
        print(f"\n🎉 所有步骤已完成！当前：{current_name}")
    else:
        if current_step == 1:
            next_step = 1.5
        elif current_step == 1.5:
            next_step = 2
        else:
            next_step = current_step + 1
        next_name = step_names.get(next_step, f"步骤{next_step}")
        options = [f"继续--{next_name}", f"重做--{current_name}", "退出"]
    
    while True:
        try:
            print("\n请选择操作:")
            for i, option in enumerate(options, 1):
                print(f"  {i}. {option}")
            
            choice = input(f"请输入序号 (1-{len(options)}) 或 'q' 退出 (默认 1): ").strip()
            
            if choice == "" or choice == "1":
                return "next" if current_step < 5 else "redo"
            elif choice == "2":
                return "redo" if current_step < 5 else None
            elif choice == "3" and current_step < 5:
                return None
            elif choice.lower() == 'q':
                return None
            else:
                print(f"❌ 无效输入，请输入 1-{len(options)} 之间的数字")
                
        except KeyboardInterrupt:
            print("\n操作已取消")
            return None


# ============================================================================
# 以下函数从 utils.py 移动过来，专用于CLI用户交互
# ============================================================================

def prompt_yes_no(message: str, default: bool = True) -> bool:
    """命令行确认提示，返回布尔。
    
    Args:
        message: 提示消息
        default: 默认选择（回车时采用）
    """
    try:
        suffix = "[Y/n]" if default else "[y/N]"
        # 统一在提示前输出一个空行，避免在调用点散落打印
        print()
        while True:
            choice = input(f"{message} {suffix}: ").strip().lower()
            if choice == '' and default is not None:
                return default
            if choice in ['y', 'yes', '是']:
                return True
            if choice in ['n', 'no', '否']:
                return False
            print("请输入 y 或 n")
    except KeyboardInterrupt:
        print("\n操作已取消")
        return False


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