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

from config import config, Config
from core.utils import load_json_file, logger
from core.document_processor import export_raw_to_docx
from core.routers import (
    read_document,
    intelligent_summarize,
    extract_keywords,
    generate_description_summary,
)
from core.media import (
    generate_opening_image,
    generate_images_for_segments,
    generate_cover_images,
    synthesize_voice_for_segments,
)
from core.video_composer import VideoComposer
from core.services import text_to_audio_bytedance
from core.validators import auto_detect_server_from_model


def _initialize_project(raw_data: Dict[str, Any], output_dir: str) -> tuple:
    """Create project folder structure and persist raw outputs."""
    current_time = datetime.datetime.now()
    time_suffix = current_time.strftime("%m%d_%H%M")
    raw_title = raw_data.get('title', 'untitled') or 'untitled'
    project_folder = f"{raw_title}_{time_suffix}"
    project_output_dir = os.path.join(output_dir, project_folder)

    os.makedirs(project_output_dir, exist_ok=True)
    os.makedirs(os.path.join(project_output_dir, "images"), exist_ok=True)
    os.makedirs(os.path.join(project_output_dir, "voice"), exist_ok=True)
    os.makedirs(os.path.join(project_output_dir, "text"), exist_ok=True)

    raw_json_path = os.path.join(project_output_dir, 'text', 'raw.json')
    with open(raw_json_path, 'w', encoding='utf-8') as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)

    raw_docx_path = os.path.join(project_output_dir, 'text', 'raw.docx')
    try:
        export_raw_to_docx(raw_data, raw_docx_path)
    except Exception:
        raw_docx_path = None

    return project_output_dir, raw_json_path, raw_docx_path


def _resolve_bgm_audio_path(bgm_filename: Optional[str], project_root: str) -> Optional[str]:
    """Locate BGM asset either via absolute path or music directory."""
    if not bgm_filename:
        return None
    if os.path.isabs(bgm_filename) and os.path.exists(bgm_filename):
        return bgm_filename
    candidate = os.path.join(project_root, "music", bgm_filename)
    if os.path.exists(candidate):
        return candidate
    return None


def _ensure_opening_narration(
    script_data: Optional[Dict[str, Any]],
    voice_dir: str,
    voice: str,
    opening_quote: bool,
    announce: bool = False,
    force_regenerate: bool = False,
) -> Optional[str]:
    """Generate or reuse opening narration audio when required."""
    opening_golden_quote = (script_data or {}).get("golden_quote", "")
    if not (opening_quote and isinstance(opening_golden_quote, str) and opening_golden_quote.strip()):
        return None

    try:
        os.makedirs(voice_dir, exist_ok=True)
        opening_path = os.path.join(voice_dir, "opening.wav")
        if force_regenerate and os.path.exists(opening_path):
            try:
                os.remove(opening_path)
            except Exception:
                if announce:
                    print("⚠️ 开场音频删除失败，尝试直接覆盖")

        if os.path.exists(opening_path):
            if announce:
                print(f"✅ 开场音频已存在: {opening_path}")
            return opening_path

        ok = text_to_audio_bytedance(opening_golden_quote, opening_path, voice=voice, encoding="wav")
        if ok:
            if announce:
                print(f"✅ 开场音频已生成: {opening_path}")
            return opening_path
        if announce:
            print("❌ 开场音频生成失败")
    except Exception:
        if announce:
            print("❌ 开场音频生成失败")
    return None


def _resolve_description_source_text(
    project_output_dir: str,
    raw_data: Optional[Dict[str, Any]] = None,
    script_data: Optional[Dict[str, Any]] = None,
) -> str:
    """Prefer raw.docx edits when building description-mode summary input."""
    docx_path = os.path.join(project_output_dir, 'text', 'raw.docx')
    if os.path.exists(docx_path):
        try:
            from core.document_processor import parse_raw_from_docx

            parsed = parse_raw_from_docx(docx_path)
            content = (parsed.get('content') or '').strip()
            if content:
                return content
        except Exception as exc:
            logger.warning(f"解析raw.docx失败，改用备用内容: {exc}")

    if raw_data:
        content = (raw_data.get('content') or '').strip()
        if content:
            return content

    if script_data:
        segments = script_data.get('segments') or []
        merged = "\n".join(seg.get('content', '') for seg in segments).strip()
        if merged:
            return merged

    return ""



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
    images_method: str,
    enable_subtitles: bool,
    bgm_filename: Optional[str] = None,
    opening_quote: bool = True,
    video_size: Optional[str] = None,
    cover_image_size: Optional[str] = None,
    cover_image_model: Optional[str] = None,
    cover_image_style: Optional[str] = None,
    cover_image_count: int = 1,
) -> Dict[str, Any]:
    start_time = datetime.datetime.now()

    project_root = os.path.dirname(os.path.dirname(__file__))
    images_method = images_method or getattr(config, "SUPPORTED_IMAGE_METHODS", ["keywords"])[0]

    # 1) 读取文档
    document_content, original_length = read_document(input_file)

    # 2) 智能缩写（原始数据）
    raw_data = intelligent_summarize(
        llm_server, llm_model, document_content, target_length, num_segments
    )

    # 3) 创建输出目录结构
    project_output_dir, _, _ = _initialize_project(raw_data, output_dir)
    voice_dir = os.path.join(project_output_dir, "voice")

    # 5) 步骤1.5：段落切分
    step15 = run_step_1_5(project_output_dir, num_segments, is_new_project=True, raw_data=raw_data, auto_mode=True)
    if not step15.get("success"):
        return {"success": False, "message": step15.get("message", "步骤1.5处理失败")}
    script_data = step15.get("script_data")
    script_path = step15.get("script_path")

    # 6) 生成第二阶段产物（关键词或描述）
    keywords_data: Optional[Dict[str, Any]] = None
    keywords_path: Optional[str] = None
    description_data: Optional[Dict[str, Any]] = None
    description_path: Optional[str] = None

    if images_method == 'description':
        description_source = _resolve_description_source_text(
            project_output_dir, raw_data=raw_data
        )
        description_data = generate_description_summary(
            llm_server, llm_model, description_source, max_chars=200
        )
        description_path = os.path.join(project_output_dir, 'text', 'mini_summary.json')
        with open(description_path, 'w', encoding='utf-8') as f:
            json.dump(description_data, f, ensure_ascii=False, indent=2)
    else:
        keywords_data = extract_keywords(llm_server, llm_model, script_data)
        keywords_path = os.path.join(project_output_dir, 'text', 'keywords.json')
        with open(keywords_path, 'w', encoding='utf-8') as f:
            json.dump(keywords_data, f, ensure_ascii=False, indent=2)

    # 7) 生成开场图像（可选）& 段落图像
    images_dir = os.path.join(project_output_dir, 'images')
    opening_image_path = generate_opening_image(
        image_server, image_model, opening_image_style, image_size, images_dir, opening_quote
    )
    image_result = generate_images_for_segments(
        image_server, image_model, script_data, image_style_preset, image_size, images_dir,
        images_method=images_method,
        keywords_data=keywords_data,
        description_data=description_data,
        llm_model=llm_model,
        llm_server=llm_server,
    )
    image_paths: List[str] = image_result.get('image_paths', [])
    failed_image_segments: List[int] = image_result.get('failed_segments', [])

    if failed_image_segments:
        failed_str = '、'.join(str(idx) for idx in failed_image_segments)
        return {
            'success': False,
            'message': f"第 {failed_str} 段图像生成失败，请调整提示或稍后重试。",
            'failed_image_segments': failed_image_segments,
            'needs_retry': True,
            'stage': 3,
            'image_paths': image_paths,
        }

    # 8) 语音合成（含SRT导出）
    audio_paths = synthesize_voice_for_segments(tts_server, voice, script_data, voice_dir)

    # 9) BGM路径解析
    bgm_audio_path = _resolve_bgm_audio_path(bgm_filename, project_root)

    # 10) 开场金句口播（可选）
    opening_golden_quote = (script_data or {}).get("golden_quote", "")
    opening_narration_audio_path = _ensure_opening_narration(
        script_data, voice_dir, voice, opening_quote
    )

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
        image_size=(video_size or image_size),
        opening_quote=opening_quote,
    )

    # 12) 封面图像生成
    cover_result = None
    try:
        cover_result = _run_cover_generation(
            project_output_dir,
            cover_image_size or image_size,
            cover_image_model or image_model,
            cover_image_style or "cover01",
            max(1, int(cover_image_count or 1)),
            script_data,
            raw_data,
        )
    except Exception as e:
        logger.warning(f"封面生成失败: {e}")

    # 13) 汇总结果
    end_time = datetime.datetime.now()
    execution_time = (end_time - start_time).total_seconds()
    compression_ratio = (1 - (script_data['total_length'] / original_length)) * 100 if original_length > 0 else 0.0

    result: Dict[str, Any] = {
        'success': True,
        'message': '视频制作完成',
        'execution_time': execution_time,
        'script': {
            'file_path': script_path,
            'total_length': script_data['total_length'],
            'segments_count': script_data['actual_segments'],
        },
        'images_method': images_method,
        'images': image_paths,
        'audio_files': audio_paths,
        'final_video': final_video_path,
        'cover_images': (cover_result or {}).get('cover_paths', []),
        'statistics': {
            'original_length': original_length,
            'compression_ratio': f"{compression_ratio:.1f}%",
            'total_processing_time': execution_time,
        },
        'project_output_dir': project_output_dir,
        'failed_image_segments': failed_image_segments,
    }

    if keywords_data and keywords_path:
        total_kw = sum(
            len(seg.get('keywords', [])) + len(seg.get('atmosphere', []))
            for seg in keywords_data.get('segments', [])
        )
        result['keywords'] = {
            'file_path': keywords_path,
            'total_keywords': total_kw,
            'avg_per_segment': total_kw / max(1, len(keywords_data.get('segments', [])))
            if keywords_data.get('segments') else 0,
        }

    if description_data and description_path:
        result['mini_summary'] = {
            'file_path': description_path,
            'summary_length': description_data.get('total_length', len(description_data.get('summary', ''))),
        }

    if cover_result:
        result['cover_generation'] = cover_result

    return result


__all__ = ["run_auto"]


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

    project_output_dir, raw_json_path, raw_docx_path = _initialize_project(raw_data, output_dir)

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
    from core.utils import load_json_file, logger, logger
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


def run_step_2(
    llm_server: str,
    llm_model: str,
    project_output_dir: str,
    script_path: str = None,
    images_method: str = "keywords",
) -> Dict[str, Any]:
    script_data = load_json_file(script_path) if script_path else load_json_file(
        os.path.join(project_output_dir, 'text', 'script.json')
    )
    if script_data is None:
        return {"success": False, "message": "未找到脚本数据，请先完成步骤1.5"}

    images_method = images_method or getattr(config, "SUPPORTED_IMAGE_METHODS", ["keywords"])[0]

    if images_method == "description":
        raw_path = os.path.join(project_output_dir, 'text', 'raw.json')
        raw_data = load_json_file(raw_path) if os.path.exists(raw_path) else None
        description_source = _resolve_description_source_text(
            project_output_dir, raw_data=raw_data, script_data=script_data
        )
        description_data = generate_description_summary(
            llm_server, llm_model, description_source or "", max_chars=200
        )
        description_path = os.path.join(project_output_dir, 'text', 'mini_summary.json')
        with open(description_path, 'w', encoding='utf-8') as f:
            json.dump(description_data, f, ensure_ascii=False, indent=2)
        return {"success": True, "mini_summary_path": description_path}

    keywords_data = extract_keywords(llm_server, llm_model, script_data)
    keywords_path = os.path.join(project_output_dir, 'text', 'keywords.json')
    with open(keywords_path, 'w', encoding='utf-8') as f:
        json.dump(keywords_data, f, ensure_ascii=False, indent=2)
    return {"success": True, "keywords_path": keywords_path}


def run_step_3(
    image_server: str,
    image_model: str,
    image_size: str,
    image_style_preset: str,
    project_output_dir: str,
    opening_image_style: str,
    images_method: str = "keywords",
    opening_quote: bool = True,
    target_segments: Optional[List[int]] = None,
    regenerate_opening: bool = True,
    llm_model: Optional[str] = None,
    llm_server: Optional[str] = None,
) -> Dict[str, Any]:
    images_dir = os.path.join(project_output_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)

    script_path = os.path.join(project_output_dir, 'text', 'script.json')
    script_data = load_json_file(script_path)
    if script_data is None:
        return {"success": False, "message": "未找到脚本数据，请先完成步骤1.5"}

    segments = script_data.get('segments', [])
    total_segments = len(segments)
    if total_segments == 0:
        return {"success": False, "message": "脚本中缺少段落内容"}

    selected_segments: Optional[List[int]] = None
    if target_segments is not None:
        raw_targets = list(target_segments)
        parsed_targets: List[int] = []
        for value in raw_targets:
            try:
                parsed_targets.append(int(value))
            except (TypeError, ValueError):
                continue
        selected_segments = sorted({idx for idx in parsed_targets if 1 <= idx <= total_segments})
        if raw_targets and not selected_segments:
            return {
                "success": False,
                "message": f"段落选择无效，请输入 1-{total_segments} 之间的数字",
            }

    images_method = images_method or getattr(config, "SUPPORTED_IMAGE_METHODS", ["keywords"])[0]

    if llm_model and not llm_server:
        llm_server = auto_detect_server_from_model(llm_model, "llm")

    keywords_data = None
    description_data = None
    if images_method == 'description':
        description_path = os.path.join(project_output_dir, 'text', 'mini_summary.json')
        description_data = load_json_file(description_path)
        if description_data is None:
            return {"success": False, "message": "未找到描述小结，请先执行步骤2生成描述"}
    else:
        keywords_path = os.path.join(project_output_dir, 'text', 'keywords.json')
        keywords_data = load_json_file(keywords_path)
        if keywords_data is None:
            return {"success": False, "message": "未找到关键词数据，请先执行步骤2生成关键词"}

    opening_image_path = None
    opening_image_file = os.path.join(images_dir, 'opening.png')
    opening_previously_exists = os.path.exists(opening_image_file)
    opening_regenerated = False
    if opening_quote:
        need_refresh = regenerate_opening or not opening_previously_exists
        if need_refresh:
            opening_image_path = generate_opening_image(
                image_server, image_model, opening_image_style, image_size, images_dir, opening_quote
            )
            opening_regenerated = bool(opening_image_path)
        elif opening_previously_exists:
            opening_image_path = opening_image_file
            print(f"保持现有开场图像: {opening_image_path}")

    should_generate_segments = selected_segments is None or len(selected_segments) > 0

    if should_generate_segments:
        generation_targets = None if selected_segments is None else selected_segments
        image_result = generate_images_for_segments(
            image_server,
            image_model,
            script_data,
            image_style_preset,
            image_size,
            images_dir,
            images_method=images_method,
            keywords_data=keywords_data,
            description_data=description_data,
            target_segments=generation_targets,
            llm_model=llm_model,
            llm_server=llm_server,
        )
    else:
        image_paths = []
        for idx in range(1, total_segments + 1):
            segment_path = os.path.join(images_dir, f"segment_{idx}.png")
            image_paths.append(segment_path if os.path.exists(segment_path) else "")
        image_result = {
            'image_paths': image_paths,
            'failed_segments': [],
            'processed_segments': [],
        }

    failed_segments = image_result.get('failed_segments', [])

    if failed_segments:
        failed_str = '、'.join(str(idx) for idx in failed_segments)
        return {
            'success': False,
            'message': f"第 {failed_str} 段图像生成失败，请调整提示或稍后重试。",
            'failed_segments': failed_segments,
            'image_paths': image_result.get('image_paths', []),
            'opening_image_path': opening_image_path,
        }

    processed_segments = image_result.get('processed_segments', [])
    if selected_segments is None:
        message = "段落图像生成完成"
        if opening_regenerated:
            message += "，开场图像已更新"
    elif processed_segments:
        seg_text = '、'.join(str(idx) for idx in processed_segments)
        message = f"已生成第 {seg_text} 段图像"
        if opening_regenerated:
            message += " 并刷新开场图像"
    else:
        message = "未生成新的段落图像"
        if opening_regenerated:
            message = "已重新生成开场图像"

    result_payload = {
        'success': True,
        'opening_image_path': opening_image_path,
        'processed_segments': processed_segments,
        'message': message,
    }
    for key, value in image_result.items():
        if key != 'processed_segments':
            result_payload[key] = value
    return result_payload


def run_step_4(
    tts_server: str,
    voice: str,
    project_output_dir: str,
    opening_quote: bool = True,
    target_segments: Optional[List[int]] = None,
    regenerate_opening: bool = True,
) -> Dict[str, Any]:
    # 确保必要的文件夹存在
    voice_dir = os.path.join(project_output_dir, 'voice')
    os.makedirs(voice_dir, exist_ok=True)

    script_path = os.path.join(project_output_dir, 'text', 'script.json')
    script_data = load_json_file(script_path)
    if script_data is None:
        return {"success": False, "message": "未找到脚本数据，请先完成步骤1.5"}

    segments = script_data.get('segments', [])
    total_segments = len(segments)
    if total_segments == 0:
        return {"success": False, "message": "脚本中缺少段落内容"}

    selected_segments: Optional[List[int]] = None
    if target_segments is not None:
        raw_targets = list(target_segments)
        parsed_targets: List[int] = []
        for value in raw_targets:
            try:
                parsed_targets.append(int(value))
            except (TypeError, ValueError):
                continue
        selected_segments = sorted({idx for idx in parsed_targets if 1 <= idx <= total_segments})
        if raw_targets and not selected_segments:
            return {
                "success": False,
                "message": f"段落选择无效，请输入 1-{total_segments} 之间的数字",
            }

    generation_targets = None if selected_segments is None else selected_segments
    audio_paths = synthesize_voice_for_segments(
        tts_server,
        voice,
        script_data,
        voice_dir,
        target_segments=generation_targets,
    )

    opening_audio_file = os.path.join(voice_dir, 'opening.wav')
    opening_previously_exists = os.path.exists(opening_audio_file)
    narration_path = _ensure_opening_narration(
        script_data,
        voice_dir,
        voice,
        opening_quote,
        announce=True,
        force_regenerate=regenerate_opening,
    )

    opening_refreshed = bool(
        opening_quote and narration_path and (regenerate_opening or not opening_previously_exists)
    )

    processed_segments = (
        list(range(1, total_segments + 1)) if selected_segments is None else list(selected_segments)
    )
    if selected_segments is None:
        message = "段落语音生成完成"
        if opening_refreshed:
            message += "，开场金句音频已更新"
    elif processed_segments:
        seg_text = '、'.join(str(idx) for idx in processed_segments)
        message = f"已生成第 {seg_text} 段语音"
        if opening_refreshed:
            message += " 并刷新开场金句音频"
    else:
        message = "未生成新的段落语音"
        if opening_refreshed:
            message = "已重新生成开场金句音频"

    return {
        "success": True,
        "audio_paths": audio_paths,
        "processed_segments": processed_segments,
        "message": message,
    }


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
        audio_wav = os.path.join(voice_dir, f"voice_{i}.wav")
        audio_mp3 = os.path.join(voice_dir, f"voice_{i}.mp3")
        if os.path.exists(audio_wav) or os.path.exists(audio_mp3):
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
    audio_paths = []
    for i in range(1, script_data.get('actual_segments', 0) + 1):
        audio_wav = os.path.join(voice_dir, f"voice_{i}.wav")
        audio_mp3 = os.path.join(voice_dir, f"voice_{i}.mp3")
        if os.path.exists(audio_wav):
            audio_paths.append(audio_wav)
        elif os.path.exists(audio_mp3):
            audio_paths.append(audio_mp3)

    # BGM
    bgm_audio_path = _resolve_bgm_audio_path(bgm_filename, project_root)

    # Opening assets
    opening_image_candidate = os.path.join(images_dir, "opening.png")
    opening_image_candidate = opening_image_candidate if os.path.exists(opening_image_candidate) else None
    opening_golden_quote = (script_data or {}).get("golden_quote", "")
    opening_narration_audio_path = _ensure_opening_narration(
        script_data, voice_dir, voice, opening_quote
    )

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


def run_step_6(
    project_output_dir: str,
    cover_image_size: str,
    cover_image_model: str,
    cover_image_style: str,
    cover_image_count: int,
) -> Dict[str, Any]:
    text_dir = os.path.join(project_output_dir, 'text')
    raw_path = os.path.join(text_dir, 'raw.json')
    if not os.path.exists(raw_path):
        return {"success": False, "message": "缺少 raw.json，请先完成步骤1"}

    raw_data = load_json_file(raw_path)
    if raw_data is None:
        return {"success": False, "message": "raw.json 加载失败"}

    script_path = os.path.join(project_output_dir, 'text', 'script.json')
    script_data = load_json_file(script_path) if os.path.exists(script_path) else None

    try:
        cover_result = _run_cover_generation(
            project_output_dir,
            cover_image_size,
            cover_image_model,
            cover_image_style,
            cover_image_count,
            script_data,
            raw_data,
        )
        return {"success": True, **cover_result}
    except Exception as e:
        return {"success": False, "message": str(e)}


__all__ += [
    "run_step_1",
    "run_step_1_5",
    "run_step_2",
    "run_step_3",
    "run_step_4",
    "run_step_5",
]


def _run_cover_generation(
    project_output_dir: str,
    cover_image_size: Optional[str],
    cover_image_model: Optional[str],
    cover_image_style: Optional[str],
    cover_image_count: int,
    script_data: Optional[Dict[str, Any]],
    raw_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not script_data and not raw_data:
        raise ValueError("缺少脚本或原始数据")

    base = script_data or raw_data or {}
    video_title = base.get("title") or "未命名视频"
    content_title = base.get("content_title") or video_title
    cover_subtitle = base.get("cover_subtitle") or ""

    cover_image_size = cover_image_size or config.DEFAULT_IMAGE_SIZE
    cover_image_model = cover_image_model or config.RECOMMENDED_MODELS["image"].get("doubao", ["doubao-seedream-4-0-250828"])[0]
    cover_image_style = cover_image_style or "cover01"

    image_server = auto_detect_server_from_model(cover_image_model, "image")
    try:
        Config.validate_parameters(
            target_length=config.MIN_TARGET_LENGTH,
            num_segments=config.MIN_NUM_SEGMENTS,
            llm_server=config.SUPPORTED_LLM_SERVERS[0],
            image_server=image_server,
            tts_server=config.SUPPORTED_TTS_SERVERS[0],
            image_model=cover_image_model,
            image_size=cover_image_size,
        )
    except Exception as e:
        raise ValueError(f"封面参数校验失败: {e}")

    return generate_cover_images(
        project_output_dir,
        image_server,
        cover_image_model,
        cover_image_size,
        cover_image_style,
        max(1, int(cover_image_count or 1)),
        video_title,
        content_title,
        cover_subtitle,
    )


__all__.append("run_step_6")
