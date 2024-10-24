import os
from functions import (
    content_parser, parsed_saver, generate_and_save_images, 
    prepare_images_for_video, create_media, content
)

def main(content, num_plots=5, 
         num_images=1, image_size="1024x1024",
         llm_server="siliconflow", llm_model="Qwen/Qwen2.5-72B-Instruct-128K", 
         image_server=None, image_model="black-forest-labs/FLUX.1-schnell", 
         tts_server=None, voice="alloy", 
         generate_video=False, output_dir=None):
    
    try:
        # Input validation
        if not isinstance(content, str) or len(content) < 1000:
            raise ValueError("content必须是至少 1000 个字符的字符串")
        if not 1 < num_plots <= 20:
            raise ValueError("num_plots必须在 2 到 20 之间")
        if not 0 <= num_images <= 10:
            raise ValueError("num_images必须在 0 到 10 之间")
        if llm_server not in ["openai", "siliconflow"]:  
            raise ValueError("llm_server必须是'openai'或'siliconflow'")
        if image_server and image_server not in ["openai", "siliconflow"]:
            raise ValueError("image_server必须是'openai'或'siliconflow'或None")
        if tts_server and tts_server not in ["openai", "azure"]:
            raise ValueError("tts_server必须是'openai'或'azure'或None")

        # Create base folders
        base_dir = output_dir or os.path.expanduser("~/Desktop")
        visualization_folder = os.path.join(base_dir, "Content Visualization")
        os.makedirs(visualization_folder, exist_ok=True)
        
        # Process content
        parsed_content = content_parser(llm_server, llm_model, content, num_plots)
        if not parsed_content:
            raise ValueError("无法解析内容。")
        parsed_saver(parsed_content, visualization_folder)
        
        # Initialize return values
        result = {
            "parsed_content": parsed_content,
            "images": None,
            "image_prompts": None,
            "final_video": None,
            "audio_paths": None
        }
        
        # Handle image generation
        if image_server:
            images_folder = os.path.join(visualization_folder, "Images")
            os.makedirs(images_folder, exist_ok=True)
            image_paths, prompt_file = generate_and_save_images(
                image_server, image_model, llm_server, llm_model,
                parsed_content, num_plots, num_images, image_size, images_folder
            )
            result["images"] = image_paths
            result["image_prompts"] = prompt_file
        else:
            print("跳过图片生成。")
            
        # Handle audio generation
        if tts_server:
            audio_folder = os.path.join(visualization_folder, "Audio")
            os.makedirs(audio_folder, exist_ok=True)
            audio_paths = create_media(
                parsed_content, 
                audio_paths=audio_folder,
                image_paths=None,
                video_paths=None,
                generate_video=False,
                server=tts_server,
                voice=voice
            )
            result["audio_paths"] = audio_paths
        else:
            print("跳过音频生成。")
            
        # Handle video generation
        if generate_video and image_server and tts_server:
            video_folder = os.path.join(visualization_folder, "Video")
            os.makedirs(video_folder, exist_ok=True)
            
            selected_images = prepare_images_for_video(images_folder, num_plots, num_images)
            if not selected_images:
                raise ValueError("无法获取视频所需的图片。")
                
            media_path = create_media(
                parsed_content,
                audio_paths=audio_folder,
                image_paths=selected_images,
                video_paths=video_folder,
                generate_video=True,
                server=tts_server,
                voice=voice
            )
            result["final_video"] = media_path
        else:
            print("跳过视频合成。")

        return result
    
    except ValueError as ve:
        print(f"输入错误: {str(ve)}")
    except Exception as e:
        print(f"发生错误: {str(e)}")
    return None

# Run the main function
if __name__ == "__main__":
    result = main(content, num_plots=5, 
                 num_images=1,
                 image_size="1024x576", 
                 llm_server="openai",
                 llm_model="gpt-4",
                 image_server="siliconflow",
                 image_model="black-forest-labs/FLUX.1-schnell", 
                 tts_server="openai",
                 voice="alloy", 
                 generate_video=False)
    
    if result:
        if result["final_video"]:
            print("好耶!AIGC任务已成功完成,包括完整的内容创建!")
        elif result["images"]:
            print("AIGC任务已完成图片生成。")
        elif result["audio_paths"]:
            print("AIGC任务已完成音频生成。")
        else:
            print("AIGC任务已完成内容解析。")
    else:
        print("由于出现错误,无法完成任务。")