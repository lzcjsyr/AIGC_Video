import os
import sys
import datetime
from typing import Dict, Any

# Allow running this file directly: ensure project root is on sys.path
_CURRENT_DIR = os.path.dirname(__file__)
_PROJECT_ROOT = os.path.dirname(_CURRENT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 首先配置CLI专用日志
from cli.ui_helpers import setup_cli_logging
setup_cli_logging()

from config import config
from core.validators import validate_startup_args
from core.pipeline import (
    run_auto,
    run_step_1,
    run_step_1_5,
    run_step_2,
    run_step_3,
    run_step_4,
    run_step_5,
)
from cli.ui_helpers import (
    prompt_choice,
    interactive_file_selector,
    interactive_project_selector,
    print_section,
)

"""
命令行参数使用说明（简版）：

关键参数（均可按需覆盖）：
- input_file: 输入文档路径；为空时进入交互选择
- target_length: 目标字数（范围由 config.MIN_TARGET_LENGTH/MAX_TARGET_LENGTH 控制）
- num_segments: 分段数量（范围由 config.MIN_NUM_SEGMENTS/MAX_NUM_SEGMENTS 控制）
- image_size: 图像尺寸（必须在 config.SUPPORTED_IMAGE_SIZES 中）
- llm_model: LLM 模型名（自动识别服务商）
- image_model: 图像模型名（如 doubao-seedream-3-0-t2i-250415）
- voice: 语音音色（字节大模型音色）
- output_dir: 输出根目录（默认 output）
- image_style_preset: 段落图像风格预设（见 prompts.IMAGE_STYLE_PRESETS）
- opening_image_style: 开场图像风格（见 prompts.OPENING_IMAGE_STYLES）
- enable_subtitles: 是否启用字幕（bool）
- bgm_filename: 背景音乐文件名（从项目根目录 music/ 读取，不填则不添加BGM）

运行方式：
- CLI 包方式（推荐）：
  python -m cli

- 直接运行本文件：
  python cli/__main__.py

说明：
- 参数的边界与白名单由 config.py 配置，启动时统一校验。
- CLI 具体流程由本文件与 core/pipeline.py 实现。
"""

def _select_entry_and_context(project_root: str, output_dir: str):
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
        from cli.ui_helpers import display_project_progress_and_select_step
        
        # 检测项目进度并显示步骤选项
        progress = detect_project_progress(project_dir)
        
        # 显示完整进度状态并让用户选择要执行的步骤
        selected_step = display_project_progress_and_select_step(progress)
        if selected_step is None:
            project_dir = None
            continue
            
        step_val = selected_step
        
        return {"entry": "existing", "project_dir": project_dir, "selected_step": step_val}


def run_specific_step(
    target_step, project_output_dir, llm_server, llm_model, image_model, 
    image_size, image_style_preset, opening_image_style, tts_server, voice, 
    num_segments, enable_subtitles, bgm_filename
):
    """
    执行指定步骤并返回结果
    """
    print(f"\n正在执行步骤 {target_step}...")
    
    if target_step == 1.5:
        result = run_step_1_5(project_output_dir, num_segments)
    elif target_step == 2:
        result = run_step_2(llm_server, llm_model, project_output_dir)
    elif target_step == 3:
        result = run_step_3(image_model, image_size, image_style_preset, project_output_dir, opening_image_style)
    elif target_step == 4:
        result = run_step_4(tts_server, voice, project_output_dir)
    elif target_step == 5:
        result = run_step_5(project_output_dir, image_size, enable_subtitles, bgm_filename, voice)
    else:
        result = {"success": False, "message": "无效的步骤"}
    
    return result


def run_step_by_step_loop(
    project_output_dir, initial_step, llm_server, llm_model, image_model, 
    image_size, image_style_preset, opening_image_style, tts_server, voice, 
    num_segments, enable_subtitles, bgm_filename
):
    """
    执行指定步骤，然后进入交互模式让用户选择下一步操作
    """
    from core.project_scanner import detect_project_progress
    from cli.ui_helpers import display_project_progress_and_select_step
    
    # 首先执行指定的步骤
    if initial_step > 0:
        result = run_specific_step(
            initial_step, project_output_dir, llm_server, llm_model, image_model, 
            image_size, image_style_preset, opening_image_style, tts_server, voice, 
            num_segments, enable_subtitles, bgm_filename
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
        result = run_specific_step(
            selected_step, project_output_dir, llm_server, llm_model, image_model, 
            image_size, image_style_preset, opening_image_style, tts_server, voice, 
            num_segments, enable_subtitles, bgm_filename
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


def cli_main(
    input_file=None,
    target_length: int = config.DEFAULT_TARGET_LENGTH,
    num_segments: int = config.DEFAULT_NUM_SEGMENTS,
    image_size: str = config.DEFAULT_IMAGE_SIZE,
    llm_model: str = "google/gemini-2.5-pro",
    image_model: str = "doubao-seedream-3-0-t2i-250415",
    voice: str = config.DEFAULT_VOICE,
    output_dir: str = config.DEFAULT_OUTPUT_DIR,
    image_style_preset: str = "style05",
    opening_image_style: str = "des01",
    enable_subtitles: bool = True,
    bgm_filename: str = None,
    run_mode: str = "auto",
) -> Dict[str, Any]:
    project_root = os.path.dirname(_PROJECT_ROOT) if os.path.basename(_PROJECT_ROOT) == "cli" else _PROJECT_ROOT

    if not os.path.isabs(output_dir):
        output_dir = os.path.join(project_root, output_dir)

    llm_server, image_server, tts_server = validate_startup_args(
        target_length, num_segments, image_size, llm_model, image_model, voice
    )

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
            return run_step_by_step_loop(
                project_output_dir, selection["selected_step"], 
                llm_server, llm_model, image_model, image_size, image_style_preset, 
                opening_image_style, tts_server, voice, num_segments, 
                enable_subtitles, bgm_filename
            )

    if input_file is not None and not os.path.isabs(input_file):
        input_file = os.path.join(project_root, input_file)

    if run_mode == "auto":
        result = run_auto(
            input_file, output_dir, target_length, num_segments, image_size,
            llm_server, llm_model, image_server, image_model, tts_server, voice,
            image_style_preset, opening_image_style, enable_subtitles, bgm_filename,
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
        
        return run_step_by_step_loop(
            project_output_dir, 0,  # 不执行初始步骤，直接进入交互模式
            llm_server, llm_model, image_model, image_size, image_style_preset, 
            opening_image_style, tts_server, voice, num_segments, 
            enable_subtitles, bgm_filename
        )


if __name__ == "__main__":
    print("🚀 智能视频制作系统启动 (CLI)")

    result = cli_main(
        target_length=800,
        num_segments=6,
        image_size="1280x720",
        llm_model="google/gemini-2.5-pro",
        image_model="doubao-seedream-3-0-t2i-250415",
        voice="zh_male_yuanboxiaoshu_moon_bigtts",
        image_style_preset="style05",
        opening_image_style="des01",
        enable_subtitles=True,
        bgm_filename="Ramin Djawadi - Light of the Seven.mp3"
    )

    if result.get("success"):
        if result.get("final_video"):
            print("\n🎉 视频制作完成！")
        else:
            step_msg = result.get("message") or "已完成当前步骤"
            print(f"\n✅ {step_msg}")
    else:
        msg = result.get('message', '未知错误')
        if isinstance(msg, str) and ("用户取消" in msg or "返回上一级" in msg):
            print("\n👋 已返回上一级")
        elif result.get('needs_prior_steps') or (isinstance(msg, str) and "需要先完成前置步骤" in msg):
            print(f"\nℹ️ {msg}")
        else:
            print(f"\n❌ 处理失败: {msg}")


