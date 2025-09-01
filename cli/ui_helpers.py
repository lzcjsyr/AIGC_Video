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


def prompt_step_to_rerun(current_step) -> Optional[float]:
    """
    询问用户要从哪一步开始重做。
    显示完整步骤列表，标识当前进度。
    返回内部步骤值（1.5, 2, 3, 4, 5）。
    """
    # 定义所有步骤
    all_steps = [1.5, 2, 3, 4, 5]
    step_names = ["脚本分段", "关键词提取", "AI图像生成", "语音合成", "视频合成"]
    
    print(f"\n当前项目进度：已完成到第{current_step}步")
    print("可选择的操作步骤：")
    
    # 显示完整步骤列表
    for step, name in zip(all_steps, step_names):
        marker = "✓" if step <= current_step else " "
        step_display = f"{step:.1f}" if step == 1.5 else str(int(step))
        print(f" {marker} {step_display}. {name}")
    
    # 确定默认选择
    if current_step < 5:
        next_step = 2 if current_step == 1.5 else current_step + 1
        default_choice = f"{next_step:.1f}" if next_step == 1.5 else str(int(next_step))
    else:
        default_choice = "5"
    
    valid_inputs = ["1.5", "2", "3", "4", "5"]
    
    while True:
        try:
            raw = input(f"请输入步骤号 (1.5, 2-5) 或输入 'q' 返回上一级 (默认 {default_choice}): ").strip()
            if raw == "":
                choice = default_choice
            elif raw.lower() == 'q':
                return None
            elif raw in valid_inputs:
                choice = raw
                # 重做警告
                selected_step = 1.5 if choice == "1.5" else float(choice)
                if selected_step <= current_step and selected_step != (current_step + 1 if current_step < 5 else current_step):
                    print("⚠️  注意：重做单个步骤可能导致与其他步骤的信息不匹配，请小心。")
            else:
                print(f"无效输入，请输入 1.5, 2, 3, 4, 5 中的一个。")
                continue
            
            return 1.5 if choice == "1.5" else float(choice)
            
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