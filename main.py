import os
import shutil
import json
import datetime
import glob
from functions import (
    read_document, intelligent_summarize, extract_keywords, 
    generate_images_for_segments, synthesize_voice_for_segments, 
    compose_final_video
)
from config import config


def print_section(title: str, icon: str = "➡️") -> None:
    """打印步骤分隔块，提升可读性"""
    print("\n" + "-" * 60)
    print(f"{icon} {title}")
    print("-" * 60)


def auto_detect_server_from_model(model_name: str, model_type: str) -> str:
    """
    根据模型名称自动检测服务商
    
    Args:
        model_name: 模型名称
        model_type: 模型类型 (llm/image/tts)
    
    Returns:
        str: 服务商名称
    """
    if model_type == "llm":
        # LLM模型服务商识别
        if any(prefix in model_name for prefix in ["google/", "anthropic/", "meta/"]):
            return "openrouter"
        elif any(prefix in model_name for prefix in ["zai-org/", "moonshotai/", "Qwen/"]):
            return "siliconflow"
        elif model_name.startswith("gpt-"):
            return "aihubmix"  # 使用aihubmix代理
        else:
            return "openrouter"  # 默认
    
    elif model_type == "image":
        # 图像模型服务商识别
        if "doubao" in model_name.lower() or "seedream" in model_name.lower():
            return "doubao"
        else:
            return "doubao"  # 默认
    
    elif model_type == "voice":
        # 语音服务商识别
        if "_bigtts" in model_name:
            return "bytedance"  # 字节语音合成大模型
        else:
            return "bytedance"  # 当前只支持字节语音合成
    
    return "unknown"

def main(
    input_file=None,    # 输入文件路径（EPUB或PDF文件），如为None则自动从input文件夹读取
    target_length=1000,  # 缩写后的目标字数，范围500-2000字
    num_segments=10,    # 分段数量，默认10段
    image_size="1280x720",  # 生成图片的尺寸，可选：1024x1024(1:1), 1280x720(16:9), 864x1152(3:4), 720x1280(9:16)等
    llm_model="google/gemini-2.5-pro",  # 大语言模型
    image_model="doubao-seedream-3-0-t2i-250415",  # 图像生成模型
    voice="zh_male_yuanboxiaoshu_moon_bigtts",      # 语音音色
    output_dir="output",  # 输出目录，默认为当前目录下的output文件夹
    image_style_preset="cinematic",  # 图像风格预设，可选：cinematic, documentary, artistic等
    enable_subtitles=True,  # 是否启用字幕，默认启用
    bgm_filename: str = None,  # 背景音乐文件名（位于项目根目录的 music 文件夹，常见支持：mp3/wav/m4a/aac）
    run_mode="auto"  # 运行模式：auto 全自动；step 分步确认
):
    try:
        start_time = datetime.datetime.now()
        
        # 锚定到项目根目录（本文件所在目录），避免依赖终端CWD
        project_root = os.path.dirname(__file__)
        if not os.path.isabs(output_dir):
            output_dir = os.path.join(project_root, output_dir)
        
        # 自动识别服务商
        llm_server = auto_detect_server_from_model(llm_model, "llm")
        image_server = auto_detect_server_from_model(image_model, "image") 
        tts_server = auto_detect_server_from_model(voice, "voice")
        
        # Input validation
        if not 500 <= target_length <= 2000:
            raise ValueError("target_length必须在500-2000之间")
        if not 5 <= num_segments <= 20:
            raise ValueError("num_segments必须在5-20之间")
        if llm_server not in ["openrouter", "aihubmix", "siliconflow"]:
            raise ValueError(f"不支持的LLM模型: {llm_model}，请使用支持的模型")
        if image_server not in ["doubao"]:
            raise ValueError(f"不支持的图像模型: {image_model}，请使用支持的模型")
        if tts_server not in ["bytedance"]:
            raise ValueError(f"不支持的语音模型: {voice}，请使用支持的语音")
        if image_size not in config.SUPPORTED_IMAGE_SIZES:
            print(f"\n⚠️  不支持的图像尺寸: {image_size}")
            print("支持的尺寸: " + ", ".join(config.SUPPORTED_IMAGE_SIZES))
            raise ValueError(f"请选择支持的图像尺寸")

        # 参数与服务商设置预览
        print_section("参数与服务商设置", "⚙️")
        print(f"LLM: {llm_model} ({llm_server})")
        print(f"Image: {image_model} ({image_server})")
        print(f"TTS: {voice} ({tts_server})")
        print(f"目标字数: {target_length} | 分段: {num_segments} | 图像尺寸: {image_size}")
        print()

        # 1. 入口：新建项目 或 打开现有项目（支持返回上一级的交互循环）
        if input_file is None:
            from utils import prompt_choice, interactive_file_selector, interactive_project_selector, detect_project_progress, prompt_step_to_rerun, load_json_file, clear_downstream_outputs, collect_ordered_assets

            proceed_to_processing = False
            selected_step = None
            goto_existing_branch = False
            project_output_dir = None

            while not proceed_to_processing:
                entry = prompt_choice("请选择操作", ["新建项目（从文档开始）", "打开现有项目（从output选择）"], default_index=0)
                if entry is None:
                    print("\n程序已取消")
                    return {"success": False, "message": "用户取消", "execution_time": 0, "error": "用户取消"}

                if entry.startswith("打开现有项目"):
                    # 二级循环：项目选择
                    while True:
                        project_dir = interactive_project_selector(output_dir=os.path.join(project_root, "output"))
                        if not project_dir:
                            # 返回上一级：回到主菜单
                            print("👋 返回上一级")
                            break

                        # 三级循环：步骤选择
                        while True:
                            prog = detect_project_progress(project_dir)
                            step_to_rerun = prompt_step_to_rerun(prog['current_step'])
                            if step_to_rerun is None:
                                # 返回上一级：回到项目列表
                                print("👋 返回上一级")
                                break

                            # 载入现有脚本/关键词（若存在）
                            script_path = os.path.join(project_dir, 'text', 'script.json')
                            keywords_path = os.path.join(project_dir, 'text', 'keywords.json')
                            script_data = load_json_file(script_path) if os.path.exists(script_path) else None
                            keywords_data = load_json_file(keywords_path) if os.path.exists(keywords_path) else None

                            # 清理下游产物（从第2步及之后开始重做时）
                            if step_to_rerun >= 2:
                                clear_downstream_outputs(project_dir, from_step=step_to_rerun)

                            # 根据选择的步骤进行处理分支
                            if step_to_rerun == 1:
                                # 需要重新读取文档 -> 无源文件信息，提示用户重新选择输入文档
                                print("将从第1步重做（智能缩写），需要源文档。")
                                input_file = interactive_file_selector(input_dir=os.path.join(project_root, "input"))
                                if input_file is None:
                                    # 返回上一级：回到项目步骤选择
                                    print("👋 返回上一级")
                                    continue
                                # 继续后续逻辑，如新建项目（但复用已选参数），并将输出生成到新的项目目录
                                goto_existing_branch = False
                                selected_step = 2  # 标记仅完成第1步后返回（沿用下方逻辑判断）
                                proceed_to_processing = True
                                break
                            elif step_to_rerun == 2:
                                if not script_data:
                                    return {"success": False, "message": "当前项目缺少 script.json，无法从第2步开始"}
                                project_output_dir = project_dir
                            elif step_to_rerun == 3:
                                if not keywords_data or not script_data:
                                    return {"success": False, "message": "当前项目缺少 keywords 或 script，无法从第3步开始"}
                                project_output_dir = project_dir
                            elif step_to_rerun == 4:
                                if not script_data:
                                    return {"success": False, "message": "当前项目缺少 script.json，无法从第4步开始"}
                                project_output_dir = project_dir
                            elif step_to_rerun == 5:
                                if not script_data:
                                    return {"success": False, "message": "当前项目缺少 script.json，无法从第5步开始"}
                                project_output_dir = project_dir
                            else:
                                return {"success": False, "message": "无效的步骤"}

                            # 设置模式：在“打开现有项目并选择具体步骤重做”的场景下，直接执行该步，跳过处理方式与分步确认
                            run_mode = "auto"
                            selected_step = step_to_rerun
                            goto_existing_branch = step_to_rerun >= 2
                            # 完成选择，跳出至处理流程
                            proceed_to_processing = True
                            break

                        if proceed_to_processing:
                            break

                    # 若未进入处理流程，则回到主菜单循环
                    if not proceed_to_processing:
                        continue

                else:
                    # 新建项目（带返回上一级）
                    # 选择源文件
                    while True:
                        input_file = interactive_file_selector(input_dir=os.path.join(project_root, "input"))
                        if input_file is None:
                            print("👋 返回上一级")
                            # 回到主菜单
                            break
                        # 选择处理方式
                        mode = prompt_choice("请选择处理方式", ["全自动（一次性全部生成）", "分步处理（每步确认并可修改产物）"], default_index=1)
                        if mode is None:
                            # 返回上一级：回到文件选择
                            print("👋 返回上一级")
                            continue
                        run_mode = "auto" if mode.startswith("全自动") else "step"
                        selected_step = None
                        proceed_to_processing = True
                        break

            # 继续进入处理流程
        # 如果提供的是相对路径，则相对于项目根目录解析（仅当存在 input_file 时）
        if input_file is not None and not os.path.isabs(input_file):
            input_file = os.path.join(project_root, input_file)

        goto_existing_branch = locals().get('goto_existing_branch', False)
        if not goto_existing_branch:
            # 合并显示：步骤 1/5 智能缩写（包含读取文档）
            print_section("步骤 1/5 智能缩写", "🧠")
            print(f"正在读取文档: {input_file}")
            document_content, original_length = read_document(input_file)
        
        # 步骤 1/5 智能缩写（包含读取文档）
        if not goto_existing_branch:
            # 保持运行逻辑不变，仅简化输出：继续执行智能缩写
            print("正在进行智能缩写处理...")
            script_data = intelligent_summarize(
                llm_server, llm_model, document_content, 
                target_length, num_segments
            )
            
            # 创建带有title+时间的输出目录结构
            current_time = datetime.datetime.now()
            time_suffix = current_time.strftime("%m%d_%H%M")
            title = script_data.get('title', 'untitled').replace(' ', '_').replace('/', '_').replace('\\', '_')
            project_folder = f"{title}_{time_suffix}"
            project_output_dir = os.path.join(output_dir, project_folder)
            
            os.makedirs(project_output_dir, exist_ok=True)
            os.makedirs(f"{project_output_dir}/images", exist_ok=True)
            os.makedirs(f"{project_output_dir}/voice", exist_ok=True)
            os.makedirs(f"{project_output_dir}/text", exist_ok=True)
            # 不再在项目输出目录创建 music 子目录，BGM 直接从项目根目录 music/ 读取
            
            print(f"\n📁 项目输出目录: {project_output_dir}")
            
            # 保存口播稿JSON
            script_path = f"{project_output_dir}/text/script.json"
            with open(script_path, 'w', encoding='utf-8') as f:
                json.dump(script_data, f, ensure_ascii=False, indent=2)
            print(f"口播稿已保存到: {script_path}")
            # 若用户明确选择只重做第1步（智能缩写），则到此为止
            if locals().get('selected_step') == 1:
                # 步骤执行完成后返回到项目选择/步骤选择界面由主程序循环控制（此处返回成功信息）
                return {"success": True, "message": "已完成第1步：智能缩写", "final_stage": "script", "script": {"file_path": script_path, "segments_count": script_data['actual_segments'], "total_length": script_data['total_length']}}
        else:
            # 已存在项目分支：project_output_dir、script_data、keywords_data 由上方分支准备
            project_output_dir = locals().get('project_output_dir')
            script_data = locals().get('script_data')
            keywords_data = locals().get('keywords_data')
            script_path = os.path.join(project_output_dir, 'text', 'script.json')
            # 原始字数在现有项目中不可得，使用脚本总字数作为基准避免计算错误
            original_length = script_data.get('total_length', 0)
        
        # 分步确认：允许用户修改 script.json 后再继续
        if run_mode == "step" and not goto_existing_branch:
            from utils import prompt_yes_no, load_json_file
            if not prompt_yes_no("是否继续到关键词提取步骤？(可先在 output/text/script.json 修改后再继续)"):
                return {"success": True, "message": "已生成脚本，用户终止于此", "final_stage": "script"}
            # 重新从磁盘加载最新脚本，确保捕获用户调整
            script_data = load_json_file(script_path)
        
        # 关键词提取：新建或从关键词步骤开始重做时执行（步骤 2/5）
        if not (goto_existing_branch and locals().get('step_to_rerun') > 2):
            print_section("步骤 2/5 关键词提取", "🧩")
            print("正在提取关键词...")
            keywords_data = extract_keywords(
                llm_server, llm_model, script_data
            )
            
            # 保存关键词JSON
            keywords_path = f"{project_output_dir}/text/keywords.json"
            with open(keywords_path, 'w', encoding='utf-8') as f:
                json.dump(keywords_data, f, ensure_ascii=False, indent=2)
            print(f"关键词已保存到: {keywords_path}")
            # 若用户明确选择只重做第2步（关键词），则到此为止
            if locals().get('selected_step') == 2:
                return {"success": True, "message": "已完成第2步：关键词提取", "final_stage": "keywords", "keywords": {"file_path": keywords_path}}
        
        if run_mode == "step" and not (goto_existing_branch and locals().get('step_to_rerun') > 2):
            from utils import prompt_yes_no, load_json_file
            if not prompt_yes_no("是否继续到图像生成步骤？(可先在 output/text/keywords.json 修改后再继续)"):
                return {"success": True, "message": "已生成关键词，用户终止于此", "final_stage": "keywords"}
            keywords_data = load_json_file(keywords_path)
        
        # 步骤 3/5 图像生成
        if not (goto_existing_branch and locals().get('step_to_rerun') > 3):
            print_section("步骤 3/5 图像生成", "🖼️")
            print("正在生成图像...")
            image_paths = generate_images_for_segments(
                image_server, image_model, keywords_data, 
                image_style_preset, image_size, f"{project_output_dir}/images"
            )
        else:
            from utils import collect_ordered_assets
            try:
                assets = collect_ordered_assets(project_output_dir, script_data)
                image_paths = assets['images']
            except FileNotFoundError as e:
                msg_text = str(e)
                if "缺少图片" in msg_text:
                    return {"success": False, "message": "当前步骤需要先完成前置步骤。请按顺序执行，或选择重做缺失步骤：建议从第3步（图像生成）开始。", "final_stage": "pending_prerequisites", "needs_prior_steps": True}
                if "缺少音频" in msg_text:
                    return {"success": False, "message": "当前步骤需要先完成前置步骤。请按顺序执行，或选择重做缺失步骤：建议从第4步（语音合成）开始。", "final_stage": "pending_prerequisites", "needs_prior_steps": True}
                return {"success": False, "message": f"资源缺失：{msg_text}", "final_stage": "pending_prerequisites", "needs_prior_steps": True}
        # 若用户明确选择只重做第3步（图像），则到此为止（仅当我们实际进行了图像生成时）
        if locals().get('selected_step') == 3:
            return {"success": True, "message": "已完成第3步：图像生成", "final_stage": "images", "images": image_paths}
        
        if run_mode == "step" and not (goto_existing_branch and locals().get('step_to_rerun') > 4):
            from utils import prompt_yes_no
            print("图像已生成至:")
            for p in image_paths:
                print(" -", p)
            if not prompt_yes_no("是否继续到语音合成步骤？(可先在 output/images 中替换图片，保持文件名不变)"):
                return {"success": True, "message": "已生成图像，用户终止于此", "final_stage": "images", "images": image_paths}
            # 再次从磁盘读取，确保捕获用户替换后的文件路径（文件名不变）
            image_paths = [os.path.join(project_output_dir, "images", os.path.basename(p)) for p in image_paths]
        
        # 步骤 4/5 语音合成
        if not (goto_existing_branch and locals().get('step_to_rerun') > 4):
            print_section("步骤 4/5 语音合成", "🔊")
            print("正在合成语音...")
            audio_paths = synthesize_voice_for_segments(
                tts_server, voice, script_data, f"{project_output_dir}/voice"
            )
        else:
            from utils import collect_ordered_assets
            try:
                assets = collect_ordered_assets(project_output_dir, script_data)
                audio_paths = assets['audio']
            except FileNotFoundError as e:
                msg_text = str(e)
                if "缺少图片" in msg_text:
                    return {"success": False, "message": "当前步骤需要先完成前置步骤。请按顺序执行，或选择重做缺失步骤：建议从第3步（图像生成）开始。", "final_stage": "pending_prerequisites", "needs_prior_steps": True}
                if "缺少音频" in msg_text:
                    return {"success": False, "message": "当前步骤需要先完成前置步骤。请按顺序执行，或选择重做缺失步骤：建议从第4步（语音合成）开始。", "final_stage": "pending_prerequisites", "needs_prior_steps": True}
                return {"success": False, "message": f"资源缺失：{msg_text}", "final_stage": "pending_prerequisites", "needs_prior_steps": True}
        # 若用户明确选择只重做第4步（语音），则到此为止（仅当我们实际进行了语音合成或已收集到序列）
        if locals().get('selected_step') == 4:
            return {"success": True, "message": "已完成第4步：语音合成", "final_stage": "audio", "audio": audio_paths}
        
        if run_mode == "step" and not (goto_existing_branch and locals().get('step_to_rerun') > 5):
            from utils import prompt_yes_no
            print("音频已生成至:")
            for p in audio_paths:
                print(" -", p)
            if not prompt_yes_no("是否继续到视频合成步骤？(可先在 output/voice 中替换音频，保持文件名不变)"):
                return {"success": True, "message": "已生成音频，用户终止于此", "final_stage": "audio", "audio": audio_paths}
            # 重新基于磁盘文件确认路径
            audio_paths = [os.path.join(project_output_dir, "voice", os.path.basename(p)) for p in audio_paths]
        
        # 步骤 5/5 视频合成
        # 5.1 资源完整性与命名规范校验（确保段数、图片、音频一一对应，编号连续 1..N）
        print_section("步骤 5/5 资源校验与视频合成", "🎬")
        from utils import validate_media_assets, prompt_yes_no
        validation = validate_media_assets(
            script_data=script_data,
            images_dir=os.path.join(project_output_dir, "images"),
            voice_dir=os.path.join(project_output_dir, "voice"),
        )
        if not validation['ok']:
            print("\n⚠️  视频合成前校验未通过：")
            for item in validation['issues']:
                print(" -", item)
            print("请到 output 相应目录修正资源（文件数量与命名必须匹配段落数量），修正后再继续。")
            if run_mode == "step":
                # 5.1.1 交互式复检：允许用户修正资源后再次校验
                if not prompt_yes_no("是否已完成调整并继续进行视频合成？"):
                    return {"success": False, "message": "视频资源校验未通过，用户终止于此", "final_stage": "validation_failed"}
                # 再次校验
                validation = validate_media_assets(
                    script_data=script_data,
                    images_dir=os.path.join(project_output_dir, "images"),
                    voice_dir=os.path.join(project_output_dir, "voice"),
                )
                if not validation['ok']:
                    return {"success": False, "message": "视频资源校验仍未通过", "issues": validation['issues']}
            else:
                return {"success": False, "message": "视频资源校验未通过", "issues": validation['issues']}

        print("\n正在合成最终视频（步骤 5/5）...")
        # 5.2 解析背景音乐绝对路径（直接从项目根目录 music/ 读取；不存在则无BGM）
        bgm_audio_path = None
        if bgm_filename:
            global_candidate = os.path.join(project_root, "music", bgm_filename)
            if os.path.exists(global_candidate):
                bgm_audio_path = global_candidate
            else:
                print(f"⚠️  未找到指定的背景音乐文件: {global_candidate}，将继续生成无背景音乐的视频")

        # 5.3 执行视频合成：图像+口播音频；可选字幕与BGM在底层函数中处理
        final_video_path = compose_final_video(
            image_paths, audio_paths, f"{project_output_dir}/final_video.mp4",
            script_data=script_data, enable_subtitles=enable_subtitles,
            bgm_audio_path=bgm_audio_path, bgm_volume=config.BGM_DEFAULT_VOLUME,
            narration_volume=config.NARRATION_DEFAULT_VOLUME
        )
        
        # 计算处理统计信息
        end_time = datetime.datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        compression_ratio = (1 - script_data['total_length'] / original_length) * 100
        
        # 输出完成信息
        # 不再打印“视频制作完成”总标识，避免分步模式下误解
        print("\n" + "="*60)
        print("步骤 5/5 完成：视频合成")
        print("="*60)
        print(f"📄 口播稿段数: {script_data['actual_segments']}")
        print(f"🖼️  生成图片数量: {len(image_paths)}")
        print(f"🔊 音频文件数量: {len(audio_paths)}")
        print(f"🎬 最终视频: {final_video_path}")
        # 运行时与配置双重控制，展示最终生效状态
        effective_subtitles = bool(enable_subtitles) and bool(getattr(config, 'SUBTITLE_CONFIG', {}).get('enabled', True))
        print(f"📝 字幕功能: {'启用' if effective_subtitles else '禁用'}")
        print(f"🎵 背景音乐: {os.path.basename(bgm_audio_path) if bgm_audio_path else '未使用'}")
        print(f"⏱️  总处理时间: {execution_time:.1f}秒")
        print("="*60)
        
        # 返回结果
        result = {
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
                "total_keywords": sum(len(seg.get('keywords', [])) + len(seg.get('atmosphere', [])) 
                                    for seg in keywords_data['segments']),
                "avg_per_segment": sum(len(seg.get('keywords', [])) + len(seg.get('atmosphere', [])) 
                                     for seg in keywords_data['segments']) / len(keywords_data['segments'])
            },
            "images": image_paths,
            "audio_files": audio_paths,
            "final_video": final_video_path,
            "statistics": {
                "original_length": original_length,
                "compression_ratio": f"{compression_ratio:.1f}%",
                "total_processing_time": execution_time,
                "llm_calls": 2,
                "image_generation_time": 0,  # Will be updated by actual implementation
                "audio_generation_time": 0,  # Will be updated by actual implementation
                "video_composition_time": 0  # Will be updated by actual implementation
            }
        }
        
        return result
    
    except KeyboardInterrupt:
        print("\n\n👋 程序被用户中断")
        return {
            "success": False,
            "message": "程序被用户中断",
            "execution_time": 0,
            "error": "KeyboardInterrupt"
        }
    except Exception as e:
        print(f"\n❌ 程序执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"处理失败: {str(e)}",
            "execution_time": 0,
            "error": str(e)
        }

# Interactive CLI Entry Point
if __name__ == "__main__":
    print("🚀 智能视频制作系统启动")
    
    # ========================================================================
    # 可选参数说明 (所有模型名称均可直接复制粘贴使用)
    # ========================================================================
    
    # 基础参数
    # target_length: 目标字数 (500-1000)
    # num_segments: 分段数量 (5-20) 
    # enable_subtitles: 是否启用字幕 (True/False)
    
    # 图像尺寸选项
    # image_size: 1024x1024 | 1280x720 | 720x1280 | 864x1152 | 1152x864 | 832x1248 | 1248x832 | 1512x648
    
    # LLM模型选项
    # llm_model:
    #     OpenRouter服务商:
    #       - google/gemini-2.5-pro （推荐）
    #       - anthropic/claude-sonnet-4  
    #       - anthropic/claude-3.7-sonnet:thinking
    #     
    #     SiliconFlow服务商:
    #       - zai-org/GLM-4.5
    #       - moonshotai/Kimi-K2-Instruct
    #       - Qwen/Qwen3-235B-A22B-Thinking-2507
    #     
    #     aihubmix服务商（OpenAI兼容代理）:
    #       - gpt-5 （暂时不可用！！！）
    
    # 图像生成模型
    # image_model: doubao-seedream-3-0-t2i-250415
    
    # 语音音色选项（可自行再豆包官网选择）
    # voice: zh_male_yuanboxiaoshu_moon_bigtts | zh_female_linjianvhai_moon_bigtts | 
    #        zh_male_yangguangqingnian_moon_bigtts | ICL_zh_female_heainainai_tob
    
    # 图像风格预设
    # image_style_preset: cinematic | documentary | artistic | minimalist | vintage
    
    # 背景音乐
    # bgm_filename: 背景音乐文件名（将音频放在项目根目录的 music/ 下，常见支持：mp3/wav/m4a/aac）；
    #               传入 None / 留空 / 错误文件名 则不使用 BGM。
    # ========================================================================
    
    # 运行主程序 - input_file设为None以启用交互式选择
    result = main(
        input_file=None,  # 启用交互式文件选择
        target_length=1000,
        num_segments=10,
        image_size="1280x720",
        llm_model="google/gemini-2.5-pro",
        image_model="doubao-seedream-3-0-t2i-250415",
        voice="zh_male_yuanboxiaoshu_moon_bigtts",
        image_style_preset="vintage",
        enable_subtitles=True,
        bgm_filename="Ramin Djawadi - Light of the Seven.mp3"  
    )
    
    if result["success"]:
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