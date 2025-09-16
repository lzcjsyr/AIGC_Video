"""
Minimal pipeline runner to simplify main.py.
Implements an auto end-to-end flow using existing core modules.

调用关系:
- cli/__main__.py: 通过VideoPipeline类执行完整的视频制作流程
- web/backend/app.py: 在后台任务中使用VideoPipeline执行视频制作
- 作为系统的核心编排模块，协调所有其他核心模块完成5步处理流程
- 调用core/routers.py的文档读取、智能总结、要点提取功能
- 调用core/media.py的图像生成、语音合成、视频合成功能
- 调用core/document_processor.py导出DOCX文档
"""

import os
import json
import datetime
from typing import Dict, Any, List, Optional

from config import config
from core.utils import load_json_file
from core.document_processor import export_raw_to_docx
from core.routers import (
    read_document,
    intelligent_summarize,
    extract_keywords,
)
from core.media import (
    generate_opening_image,
    generate_images_for_segments,
    synthesize_voice_for_segments,
)
from core.video_composer import VideoComposer
from core.services import text_to_audio_bytedance


def run_auto(
    input_file: str,
    output_dir: str,
    target_length: int,
    num_segments: int,
    image_size: str,
    llm_server: str,
    llm_model: str,
    image_server: str,
    image_model: str,
    tts_server: str,
    voice: str,
    image_style_preset: str,
    opening_image_style: str,
    enable_subtitles: bool,
    bgm_filename: Optional[str] = None,
    opening_quote: bool = True,
) -> Dict[str, Any]:
    start_time = datetime.datetime.now()

    project_root = os.path.dirname(os.path.dirname(__file__))

    # 1) 读取文档
    document_content, original_length = read_document(input_file)

    # 2) 智能缩写（原始数据）
    raw_data = intelligent_summarize(
        llm_server, llm_model, document_content, target_length, num_segments
    )

    # 3) 创建输出目录结构
    current_time = datetime.datetime.now()
    time_suffix = current_time.strftime("%m%d_%H%M")
    title = raw_data.get('title', 'untitled').replace(' ', '_').replace('/', '_').replace('\\', '_')
    project_folder = f"{title}_{time_suffix}"
    project_output_dir = os.path.join(output_dir, project_folder)
    os.makedirs(project_output_dir, exist_ok=True)
    os.makedirs(f"{project_output_dir}/images", exist_ok=True)
    os.makedirs(f"{project_output_dir}/voice", exist_ok=True)
    os.makedirs(f"{project_output_dir}/text", exist_ok=True)

    # 4) 保存原始JSON + 导出可编辑DOCX
    raw_json_path = f"{project_output_dir}/text/raw.json"
    with open(raw_json_path, 'w', encoding='utf-8') as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)
    try:
        raw_docx_path = f"{project_output_dir}/text/raw.docx"
        export_raw_to_docx(raw_data, raw_docx_path)
    except Exception:
        raw_docx_path = None

    # 5) 步骤1.5：段落切分
    step15 = run_step_1_5(project_output_dir, num_segments, is_new_project=True, raw_data=raw_data, auto_mode=True)
    if not step15.get("success"):
        return {"success": False, "message": step15.get("message", "步骤1.5处理失败")}
    script_data = step15.get("script_data")
    script_path = step15.get("script_path")

    # 6) 要点提取
    keywords_data = extract_keywords(llm_server, llm_model, script_data)
    keywords_path = f"{project_output_dir}/text/keywords.json"
    with open(keywords_path, 'w', encoding='utf-8') as f:
        json.dump(keywords_data, f, ensure_ascii=False, indent=2)

    # 7) 生成开场图像（可选）& 段落图像
    opening_image_path = generate_opening_image(
        image_model, opening_image_style, image_size, f"{project_output_dir}/images", opening_quote
    )
    image_result = generate_images_for_segments(
        image_model, keywords_data, image_style_preset, image_size, f"{project_output_dir}/images"
    )
    image_paths: List[str] = image_result["image_paths"]
    failed_image_segments: List[int] = image_result["failed_segments"]

    # 8) 语音合成（含SRT导出）
    audio_paths = synthesize_voice_for_segments(tts_server, voice, script_data, f"{project_output_dir}/voice")

    # 9) BGM路径解析
    bgm_audio_path = None
    if bgm_filename:
        candidate = os.path.join(project_root, "music", bgm_filename)
        if os.path.exists(candidate):
            bgm_audio_path = candidate

    # 10) 开场金句口播（可选）
    opening_golden_quote = (script_data or {}).get("golden_quote", "")
    opening_narration_audio_path = None
    try:
        if opening_quote and isinstance(opening_golden_quote, str) and opening_golden_quote.strip():
            opening_voice_dir = os.path.join(project_output_dir, "voice")
            os.makedirs(opening_voice_dir, exist_ok=True)
            opening_narration_audio_path = os.path.join(opening_voice_dir, "opening.wav")
            if not os.path.exists(opening_narration_audio_path):
                ok = text_to_audio_bytedance(opening_golden_quote, opening_narration_audio_path, voice=voice, encoding="wav")
                if not ok:
                    opening_narration_audio_path = None
    except Exception:
        opening_narration_audio_path = None

    # 11) 视频合成
    composer = VideoComposer()
    final_video_path = composer.compose_video(
        image_paths, audio_paths, f"{project_output_dir}/final_video.mp4",
        script_data=script_data, enable_subtitles=enable_subtitles,
        bgm_audio_path=bgm_audio_path,
        opening_image_path=opening_image_path,
        opening_golden_quote=opening_golden_quote,
        opening_narration_audio_path=opening_narration_audio_path,
        bgm_volume=float(getattr(config, "BGM_DEFAULT_VOLUME", 0.2)),
        narration_volume=float(getattr(config, "NARRATION_DEFAULT_VOLUME", 1.0)),
        image_size=image_size,
        opening_quote=opening_quote,
    )

    # 12) 汇总结果
    end_time = datetime.datetime.now()
    execution_time = (end_time - start_time).total_seconds()
    compression_ratio = (1 - (script_data['total_length'] / original_length)) * 100 if original_length > 0 else 0.0

    return {
        "success": True,
        "message": "视频制作完成",
        "execution_time": execution_time,
        "script": {
            "file_path": script_path,
            "total_length": script_data['total_length'],
            "segments_count": script_data['actual_segments']
        },
        "keywords": {
            "file_path": keywords_path,
            "total_keywords": sum(len(seg.get('keywords', [])) + len(seg.get('atmosphere', [])) for seg in keywords_data['segments']),
            "avg_per_segment": sum(len(seg.get('keywords', [])) + len(seg.get('atmosphere', [])) for seg in keywords_data['segments']) / max(1, len(keywords_data['segments']))
        },
        "images": image_paths,
        "audio_files": audio_paths,
        "final_video": final_video_path,
        "statistics": {
            "original_length": original_length,
            "compression_ratio": f"{compression_ratio:.1f}%",
            "total_processing_time": execution_time,
        },
        "project_output_dir": project_output_dir,
        "failed_image_segments": failed_image_segments,
    }


__all__ = ["run_auto"]


def run_interactive_setup(project_root: str, output_dir: str):
    """Minimal interactive setup: choose input file and run mode.

    Returns: (input_file, run_mode)
    """
    try:
        from cli.ui_helpers import prompt_choice, interactive_file_selector
        # 文件选择
        while True:
            input_file = interactive_file_selector(input_dir=os.path.join(project_root, "input"))
            if input_file is None:
                print("\n👋 返回上一级")
                continue
            mode = prompt_choice("请选择处理方式", ["全自动（一次性全部生成）", "分步处理（每步确认并可修改产物）"], default_index=0)
            if mode is None:
                print("👋 返回上一级")
                continue
            run_mode = "auto" if mode.startswith("全自动") else "step"
            return input_file, run_mode
    except Exception:
        # 发生异常时返回None，主流程自行处理
        return None, "auto"

__all__.append("run_interactive_setup")


# -------------------- Step-wise pipeline (for CLI step mode) --------------------

def run_step_1(
    input_file: str,
    output_dir: str,
    llm_server: str,
    llm_model: str,
    target_length: int,
    num_segments: int,
) -> Dict[str, Any]:
    document_content, _ = read_document(input_file)
    raw_data = intelligent_summarize(llm_server, llm_model, document_content, target_length, num_segments)

    current_time = datetime.datetime.now()
    time_suffix = current_time.strftime("%m%d_%H%M")
    title = raw_data.get('title', 'untitled').replace(' ', '_').replace('/', '_').replace('\\', '_')
    project_folder = f"{title}_{time_suffix}"
    project_output_dir = os.path.join(output_dir, project_folder)
    os.makedirs(project_output_dir, exist_ok=True)
    os.makedirs(f"{project_output_dir}/images", exist_ok=True)
    os.makedirs(f"{project_output_dir}/voice", exist_ok=True)
    os.makedirs(f"{project_output_dir}/text", exist_ok=True)

    raw_json_path = f"{project_output_dir}/text/raw.json"
    with open(raw_json_path, 'w', encoding='utf-8') as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)

    try:
        raw_docx_path = f"{project_output_dir}/text/raw.docx"
        export_raw_to_docx(raw_data, raw_docx_path)
    except Exception:
        raw_docx_path = None

    return {
        "success": True,
        "project_output_dir": project_output_dir,
        "raw": {"raw_json_path": raw_json_path, "raw_docx_path": raw_docx_path, "total_length": raw_data.get('total_length', 0)},
    }


def run_step_1_5(project_output_dir: str, num_segments: int, is_new_project: bool = False, raw_data: Optional[Dict[str, Any]] = None, auto_mode: bool = False) -> Dict[str, Any]:
    """
    统一处理步骤1.5：段落切分
    
    Args:
        project_output_dir: 项目输出目录
        num_segments: 目标分段数
        is_new_project: 是否为新建项目
        raw_data: 原始数据（新建项目时提供）
        
    Returns:
        Dict[str, Any]: 处理结果，包含成功状态和相关信息
    """
    from core.utils import load_json_file, logger
    from core.document_processor import parse_raw_from_docx, export_script_to_docx
    
    try:
        print("正在处理原始内容为脚本...")
        
        # 构建文件路径
        raw_json_path = os.path.join(project_output_dir, 'text', 'raw.json')
        raw_docx_path = os.path.join(project_output_dir, 'text', 'raw.docx')
        script_path = os.path.join(project_output_dir, 'text', 'script.json')
        script_docx_path = os.path.join(project_output_dir, 'text', 'script.docx')
        
        # 获取原始数据
        if is_new_project and raw_data is not None:
            # 新建项目：使用提供的raw_data
            logger.info(f"新建项目：使用提供的raw数据")
            current_raw_data = raw_data
        else:
            # 现有项目：从文件加载
            if not os.path.exists(raw_json_path):
                # 没有raw.json但有raw.docx，创建一个默认的raw.json
                current_raw_data = {"title": "手动创建项目", "golden_quote": "", "content": "", "target_segments": num_segments}
            else:
                print(f"加载raw数据: {raw_json_path}")
                current_raw_data = load_json_file(raw_json_path)
                if current_raw_data is None:
                    return {"success": False, "message": f"无法加载 raw.json 文件: {raw_json_path}"}
                num_segments = current_raw_data.get("target_segments", num_segments)
                print(f"当前分段数: {num_segments}")
        
        # 尝试从编辑后的DOCX文件解析数据
        updated_raw_data = current_raw_data
        if os.path.exists(raw_docx_path):
            try:
                parsed_data = parse_raw_from_docx(raw_docx_path)
                if parsed_data is not None:
                    print("已从编辑后的DOCX文件解析内容")
                    updated_raw_data = parsed_data
                    
                    # 更新元数据但保留原始信息
                    updated_raw_data.update({
                        "target_segments": current_raw_data.get("target_segments", num_segments),
                        "created_time": current_raw_data.get("created_time"),
                        "model_info": current_raw_data.get("model_info", {}),
                        "total_length": len(updated_raw_data.get("content", ""))
                    })
                    
                    # 更新raw.json文件
                    with open(raw_json_path, 'w', encoding='utf-8') as f:
                        json.dump(updated_raw_data, f, ensure_ascii=False, indent=2)
                    print(f"已更新原始JSON: {raw_json_path}")
                else:
                    print("⚠️  DOCX解析返回None，使用原始数据")
            except Exception as e:
                print(f"⚠️  解析DOCX失败，使用原始数据: {e}")
        
        # 检查最终数据
        if updated_raw_data is None:
            return {"success": False, "message": "处理raw数据失败：数据为空"}
        
        # 用户选择切分模式（仅在交互模式下）
        split_mode = "auto"  # 默认自动切分
        if not auto_mode:  # 只有非全自动模式才显示选择界面
            try:
                from cli.ui_helpers import prompt_choice
                choice = prompt_choice("请选择文本切分方式", ["手动切分(根据换行符)", "自动切分(智能均分)"], default_index=1)
                if choice and choice.startswith("手动"):
                    split_mode = "manual"
            except:
                pass  # 如果无法显示选择界面，使用默认值

        # 处理为分段脚本数据
        from core.routers import process_raw_to_script
        target_segments = updated_raw_data.get("target_segments", num_segments)
        script_data = process_raw_to_script(updated_raw_data, target_segments, split_mode)
        
        # 保存script.json
        with open(script_path, 'w', encoding='utf-8') as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)
        print(f"分段脚本已保存到: {script_path}")
        
        # 生成可阅读的script.docx
        try:
            export_script_to_docx(script_data, script_docx_path)
            print(f"阅读版DOCX已保存到: {script_docx_path}")
        except Exception as e:
            print(f"⚠️  生成script.docx失败: {e}")
        
        logger.info(f"步骤1.5处理完成: {script_path}")
        return {
            "success": True,
            "script_data": script_data,
            "script_path": script_path,
            "message": "步骤1.5处理完成"
        }
        
    except Exception as e:
        logger.error(f"步骤1.5处理失败: {str(e)}")
        return {"success": False, "message": f"步骤1.5处理失败: {str(e)}"}


def run_step_2(llm_server: str, llm_model: str, project_output_dir: str, script_path: str = None) -> Dict[str, Any]:
    script_data = load_json_file(script_path) if script_path else load_json_file(os.path.join(project_output_dir, 'text', 'script.json'))
    keywords_data = extract_keywords(llm_server, llm_model, script_data)
    keywords_path = f"{project_output_dir}/text/keywords.json"
    with open(keywords_path, 'w', encoding='utf-8') as f:
        json.dump(keywords_data, f, ensure_ascii=False, indent=2)
    return {"success": True, "keywords_path": keywords_path}


def run_step_3(image_model: str, image_size: str, image_style_preset: str, project_output_dir: str, opening_image_style: str, opening_quote: bool = True) -> Dict[str, Any]:
    # 确保必要的文件夹存在
    os.makedirs(f"{project_output_dir}/images", exist_ok=True)

    keywords_path = os.path.join(project_output_dir, 'text', 'keywords.json')
    keywords_data = load_json_file(keywords_path)
    opening_image_path = generate_opening_image(image_model, opening_image_style, image_size, f"{project_output_dir}/images", opening_quote)
    image_result = generate_images_for_segments(image_model, keywords_data, image_style_preset, image_size, f"{project_output_dir}/images")
    return {"success": True, "opening_image_path": opening_image_path, **image_result}


def run_step_4(tts_server: str, voice: str, project_output_dir: str, opening_quote: bool = True) -> Dict[str, Any]:
    # 确保必要的文件夹存在
    os.makedirs(f"{project_output_dir}/voice", exist_ok=True)

    script_path = os.path.join(project_output_dir, 'text', 'script.json')
    script_data = load_json_file(script_path)
    audio_paths = synthesize_voice_for_segments(tts_server, voice, script_data, f"{project_output_dir}/voice")

    # 生成开场音频
    opening_golden_quote = (script_data or {}).get("golden_quote", "")
    if opening_quote and isinstance(opening_golden_quote, str) and opening_golden_quote.strip():
        opening_voice_dir = os.path.join(project_output_dir, "voice")
        os.makedirs(opening_voice_dir, exist_ok=True)
        opening_narration_audio_path = os.path.join(opening_voice_dir, "opening.wav")
        if not os.path.exists(opening_narration_audio_path):
            from core.media import text_to_audio_bytedance
            ok = text_to_audio_bytedance(opening_golden_quote, opening_narration_audio_path, voice=voice, encoding="wav")
            if ok:
                print(f"✅ 开场音频已生成: {opening_narration_audio_path}")
            else:
                print("❌ 开场音频生成失败")
        else:
            print(f"✅ 开场音频已存在: {opening_narration_audio_path}")

    return {"success": True, "audio_paths": audio_paths}


def run_step_5(project_output_dir: str, image_size: str, enable_subtitles: bool, bgm_filename: str, voice: str, opening_quote: bool = True) -> Dict[str, Any]:
    project_root = os.path.dirname(os.path.dirname(__file__))
    images_dir = os.path.join(project_output_dir, 'images')
    voice_dir = os.path.join(project_output_dir, 'voice')
    script_path = os.path.join(project_output_dir, 'text', 'script.json')

    # 前置检查：确保必要文件存在
    if not os.path.exists(script_path):
        return {"success": False, "message": "脚本文件不存在，请先完成步骤1.5"}

    script_data = load_json_file(script_path)
    if not script_data:
        return {"success": False, "message": "脚本文件加载失败"}

    # 检查图像文件
    expected_segments = script_data.get('actual_segments', 0)
    image_count = 0
    for i in range(1, expected_segments + 1):
        img_path = os.path.join(images_dir, f"segment_{i}.png")
        if os.path.exists(img_path):
            image_count += 1
        else:
            # 检查视频文件
            for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.m4v']:
                vid_path = os.path.join(images_dir, f"segment_{i}{ext}")
                if os.path.exists(vid_path):
                    image_count += 1
                    break

    # 检查音频文件
    audio_count = 0
    for i in range(1, expected_segments + 1):
        audio_path = os.path.join(voice_dir, f"voice_{i}.wav")
        if os.path.exists(audio_path):
            audio_count += 1

    if image_count == 0:
        return {"success": False, "message": "未找到图像文件，请先完成步骤3"}
    if audio_count == 0:
        return {"success": False, "message": "未找到音频文件，请先完成步骤4"}
    if image_count != expected_segments:
        return {"success": False, "message": f"图像文件不完整，需要{expected_segments}个，找到{image_count}个"}
    if audio_count != expected_segments:
        return {"success": False, "message": f"音频文件不完整，需要{expected_segments}个，找到{audio_count}个"}

    # Resolve ordered assets (支持图片和视频文件)
    image_paths = []
    for i in range(1, script_data.get('actual_segments', 0) + 1):
        # 检查图片文件
        img_path = os.path.join(images_dir, f"segment_{i}.png")
        if os.path.exists(img_path):
            image_paths.append(img_path)
            continue
        # 检查视频文件
        for ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.m4v']:
            vid_path = os.path.join(images_dir, f"segment_{i}{ext}")
            if os.path.exists(vid_path):
                image_paths.append(vid_path)
                break
    audio_paths = [os.path.join(voice_dir, f"voice_{i}.wav") for i in range(1, script_data.get('actual_segments', 0) + 1) if os.path.exists(os.path.join(voice_dir, f"voice_{i}.wav"))]

    # BGM
    bgm_audio_path = None
    if bgm_filename:
        candidate = os.path.join(project_root, "music", bgm_filename)
        if os.path.exists(candidate):
            bgm_audio_path = candidate

    # Opening assets
    opening_image_candidate = os.path.join(images_dir, "opening.png")
    opening_image_candidate = opening_image_candidate if os.path.exists(opening_image_candidate) else None
    opening_golden_quote = (script_data or {}).get("golden_quote", "")
    opening_narration_audio_path = None
    try:
        if opening_quote and isinstance(opening_golden_quote, str) and opening_golden_quote.strip():
            opening_narration_audio_path = os.path.join(voice_dir, "opening.wav")
            if not os.path.exists(opening_narration_audio_path):
                ok = text_to_audio_bytedance(opening_golden_quote, opening_narration_audio_path, voice=voice, encoding="wav")
                if not ok:
                    opening_narration_audio_path = None
    except Exception:
        opening_narration_audio_path = None

    composer = VideoComposer()
    final_video_path = composer.compose_video(
        image_paths, audio_paths, f"{project_output_dir}/final_video.mp4",
        script_data=script_data, enable_subtitles=enable_subtitles,
        bgm_audio_path=bgm_audio_path,
        opening_image_path=opening_image_candidate,
        opening_golden_quote=opening_golden_quote,
        opening_narration_audio_path=opening_narration_audio_path,
        bgm_volume=float(getattr(config, "BGM_DEFAULT_VOLUME", 0.2)),
        narration_volume=float(getattr(config, "NARRATION_DEFAULT_VOLUME", 1.0)),
        image_size=image_size,
        opening_quote=opening_quote,
    )

    return {"success": True, "final_video": final_video_path}


__all__ += [
    "run_step_1",
    "run_step_1_5",
    "run_step_2",
    "run_step_3",
    "run_step_4",
    "run_step_5",
]


