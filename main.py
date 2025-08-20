import os
import json
import datetime
import glob
from functions import (
    read_document, intelligent_summarize, extract_keywords, 
    generate_images_for_segments, synthesize_voice_for_segments, 
    compose_final_video
)

def main(
    input_file=None,    # 输入文件路径（EPUB或PDF文件），如为None则自动从input文件夹读取
    target_length=800,  # 缩写后的目标字数，范围500-1000字
    num_segments=10,    # 分段数量，默认10段
    image_style="",     # 图像风格提示词，用于统一视觉风格
    image_size="1024x1024",  # 生成图片的尺寸
    llm_server="openrouter",  # 大语言模型服务商
    llm_model="google/gemini-2.5-pro",  # 大语言模型
    image_server="doubao",  # 图像生成服务商
    image_model="Doubao-lite",  # 图像生成模型
    tts_server="doubao",  # 语音合成服务商
    voice="zh_male_yuanboxiaoshu_moon_bigtts",      # 语音音色
    output_dir="output"  # 输出目录，默认为当前目录下的output文件夹
):
    
    try:
        start_time = datetime.datetime.now()
        
        # Input validation
        if not 500 <= target_length <= 1000:
            raise ValueError("target_length必须在500-1000之间")
        if not 5 <= num_segments <= 20:
            raise ValueError("num_segments必须在5-20之间")
        if llm_server not in ["openrouter", "openai", "siliconflow"]:
            raise ValueError("llm_server必须是'openrouter'、'openai'或'siliconflow'")
        if image_server not in ["doubao"]:
            raise ValueError("image_server必须是'doubao'")
        if tts_server not in ["doubao"]:
            raise ValueError("tts_server必须是'doubao'")

        # 1. 文档读取
        if input_file is None:
            # 自动从input文件夹读取文件
            input_files = glob.glob("input/*.epub") + glob.glob("input/*.pdf")
            if not input_files:
                raise ValueError("input文件夹中未找到EPUB或PDF文件")
            input_file = input_files[0]
        
        print(f"正在读取文档: {input_file}")
        document_content, original_length = read_document(input_file)
        
        # 创建输出目录结构
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(f"{output_dir}/images", exist_ok=True)
        os.makedirs(f"{output_dir}/voice", exist_ok=True)
        os.makedirs(f"{output_dir}/text", exist_ok=True)
        
        # 2. 智能缩写（第一次LLM处理）
        print("正在进行智能缩写处理...")
        script_data = intelligent_summarize(
            llm_server, llm_model, document_content, 
            target_length, num_segments
        )
        
        # 保存口播稿JSON
        script_path = f"{output_dir}/text/script.json"
        with open(script_path, 'w', encoding='utf-8') as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)
        print(f"口播稿已保存到: {script_path}")
        
        # 3. 关键词提取（第二次LLM处理）
        print("正在提取关键词...")
        keywords_data = extract_keywords(
            llm_server, llm_model, script_data
        )
        
        # 保存关键词JSON
        keywords_path = f"{output_dir}/text/keywords.json"
        with open(keywords_path, 'w', encoding='utf-8') as f:
            json.dump(keywords_data, f, ensure_ascii=False, indent=2)
        print(f"关键词已保存到: {keywords_path}")
        
        # 4. AI图像生成
        print("正在生成图像...")
        image_paths = generate_images_for_segments(
            image_server, image_model, keywords_data, 
            image_style, image_size, f"{output_dir}/images"
        )
        
        # 5. 语音合成
        print("正在合成语音...")
        audio_paths = synthesize_voice_for_segments(
            tts_server, voice, script_data, f"{output_dir}/voice"
        )
        
        # 6. 视频合成
        print("正在合成最终视频...")
        final_video_path = compose_final_video(
            image_paths, audio_paths, f"{output_dir}/final_video.mp4"
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
总处理时间: {execution_time:.1f}秒
"""
        
        summary_path = f"{output_dir}/text/summary.txt"
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary_text)
        print(f"处理摘要已保存到: {summary_path}")
        
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
    result = main(
        target_length=800,
        num_segments=10,
        image_style="电影级质感，温暖色调，细腻画风",
        image_size="1024x576",
        llm_server="openrouter",
        llm_model="google/gemini-2.5-pro",
        image_server="doubao",
        image_model="Doubao-lite",
        tts_server="doubao",
        voice="zh_female_qingxin"
    )
    
    if result and result.get("success"):
        print("视频制作完成！")
        print(f"口播稿段数: {result['script']['segments_count']}")
        print(f"生成图片数量: {len(result['images'])}")
        print(f"音频文件数量: {len(result['audio_files'])}")
        print(f"最终视频: {result['final_video']}")
    else:
        print(f"视频制作失败: {result.get('message', '未知错误')}")