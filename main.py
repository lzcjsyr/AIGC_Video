import os
import json
import datetime
import glob
from functions import (
    read_document, intelligent_summarize, extract_keywords, 
    generate_images_for_segments, synthesize_voice_for_segments, 
    compose_final_video
)
from config import config


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
            return "openai"  # aihubmix代理
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
    target_length=800,  # 缩写后的目标字数，范围500-1000字
    num_segments=10,    # 分段数量，默认10段
    image_size="1280x720",  # 生成图片的尺寸，可选：1024x1024(1:1), 1280x720(16:9), 864x1152(3:4), 720x1280(9:16)等
    llm_model="google/gemini-2.5-pro",  # 大语言模型
    image_model="doubao-seedream-3-0-t2i-250415",  # 图像生成模型
    voice="zh_male_yuanboxiaoshu_moon_bigtts",      # 语音音色
    output_dir="output",  # 输出目录，默认为当前目录下的output文件夹
    image_style_preset="cinematic",  # 图像风格预设，可选：cinematic, documentary, artistic等
    enable_subtitles=True  # 是否启用字幕，默认启用
):
    
    try:
        start_time = datetime.datetime.now()
        
        # 自动识别服务商
        llm_server = auto_detect_server_from_model(llm_model, "llm")
        image_server = auto_detect_server_from_model(image_model, "image") 
        tts_server = auto_detect_server_from_model(voice, "voice")
        
        # Input validation
        if not 500 <= target_length <= 1000:
            raise ValueError("target_length必须在500-1000之间")
        if not 5 <= num_segments <= 20:
            raise ValueError("num_segments必须在5-20之间")
        if llm_server not in ["openrouter", "openai", "siliconflow"]:
            raise ValueError(f"不支持的LLM模型: {llm_model}，请使用支持的模型")
        if image_server not in ["doubao"]:
            raise ValueError(f"不支持的图像模型: {image_model}，请使用支持的模型")
        if tts_server not in ["bytedance"]:
            raise ValueError(f"不支持的语音模型: {voice}，请使用支持的语音")
        if image_size not in config.SUPPORTED_IMAGE_SIZES:
            print(f"\n⚠️  不支持的图像尺寸: {image_size}")
            print("支持的尺寸: " + ", ".join(config.SUPPORTED_IMAGE_SIZES))
            raise ValueError(f"请选择支持的图像尺寸")

        # 1. 文档读取
        if input_file is None:
            # 自动从input文件夹读取文件
            input_files = glob.glob("input/*.epub") + glob.glob("input/*.pdf")
            if not input_files:
                raise ValueError("input文件夹中未找到EPUB或PDF文件")
            input_file = input_files[0]
        
        print(f"正在读取文档: {input_file}")
        document_content, original_length = read_document(input_file)
        
        # 2. 智能缩写（第一次LLM处理）
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
        
        print(f"项目输出目录: {project_output_dir}")
        
        # 保存口播稿JSON
        script_path = f"{project_output_dir}/text/script.json"
        with open(script_path, 'w', encoding='utf-8') as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)
        print(f"口播稿已保存到: {script_path}")
        
        # 3. 关键词提取（第二次LLM处理）
        print("正在提取关键词...")
        keywords_data = extract_keywords(
            llm_server, llm_model, script_data
        )
        
        # 保存关键词JSON
        keywords_path = f"{project_output_dir}/text/keywords.json"
        with open(keywords_path, 'w', encoding='utf-8') as f:
            json.dump(keywords_data, f, ensure_ascii=False, indent=2)
        print(f"关键词已保存到: {keywords_path}")
        
        # 4. AI图像生成
        print("正在生成图像...")
        image_paths = generate_images_for_segments(
            image_server, image_model, keywords_data, 
            image_style_preset, image_size, f"{project_output_dir}/images"
        )
        
        # 5. 语音合成
        print("正在合成语音...")
        audio_paths = synthesize_voice_for_segments(
            tts_server, voice, script_data, f"{project_output_dir}/voice"
        )
        
        # 6. 视频合成
        print("正在合成最终视频...")
        final_video_path = compose_final_video(
            image_paths, audio_paths, f"{project_output_dir}/final_video.mp4",
            script_data=script_data, enable_subtitles=enable_subtitles
        )
        
        # 生成处理摘要
        end_time = datetime.datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        compression_ratio = (1 - script_data['total_length'] / original_length) * 100
        
        summary_text = f"""=== 文档处理摘要 ===
处理时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}
原始文档: {os.path.basename(input_file)}
原始字数: {original_length:,}字
目标字数: {target_length}字
实际字数: {script_data['total_length']}字
压缩比例: {compression_ratio:.1f}%
分段数量: {num_segments}段
图像风格: {image_style_preset}
字幕功能: {'启用' if enable_subtitles else '禁用'}
总处理时间: {execution_time:.1f}秒
"""
        
        summary_path = f"{project_output_dir}/text/summary.txt"
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary_text)
        print(f"处理摘要已保存到: {summary_path}")
        
        # 输出完成信息
        print("\n" + "="*60)
        print("🎉 视频制作完成！")
        print("="*60)
        print(f"📄 口播稿段数: {script_data['actual_segments']}")
        print(f"🖼️  生成图片数量: {len(image_paths)}")
        print(f"🔊 音频文件数量: {len(audio_paths)}")
        print(f"🎬 最终视频: {final_video_path}")
        print(f"📝 字幕功能: {'启用' if enable_subtitles else '禁用'}")
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
            "text_files": {
                "summary": summary_path
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
    
    except Exception as e:
        return {
            "success": False,
            "message": f"处理失败: {str(e)}",
            "execution_time": 0,
            "error": str(e)
        }

# Run the main function
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
    #       - google/gemini-2.5-pro
    #       - anthropic/claude-sonnet-4  
    #       - anthropic/claude-3.7-sonnet:thinking
    #     
    #     SiliconFlow服务商:
    #       - zai-org/GLM-4.5
    #       - moonshotai/Kimi-K2-Instruct
    #       - Qwen/Qwen3-235B-A22B-Thinking-2507
    #     
    #     OpenAI服务商(aihubmix代理):
    #       - gpt-5
    
    # 图像生成模型
    # image_model: doubao-seedream-3-0-t2i-250415
    
    # 语音音色选项  
    # voice: zh_male_yuanboxiaoshu_moon_bigtts | zh_female_linjianvhai_moon_bigtts | 
    #        zh_male_yangguangqingnian_moon_bigtts | ICL_zh_female_heainainai_tob
    
    # 图像风格预设
    # image_style_preset: cinematic | documentary | artistic | minimalist | vintage
    # ========================================================================
    
    # 运行主程序
    main(
        target_length=800,
        num_segments=10,
        image_size="1280x720",
        llm_model="moonshotai/Kimi-K2-Instruct",
        image_model="doubao-seedream-3-0-t2i-250415",
        voice="zh_male_yuanboxiaoshu_moon_bigtts",
        image_style_preset="cinematic",
        enable_subtitles=True
    )