import os
from functions import (
    content_parser, parsed_saver, generate_and_save_images, 
    prepare_images_for_video, create_media, content
)

def main(content, num_plots=5, 
         num_images=1,image_size="1024x1024",
         llm_server="siliconflow", llm_model="Qwen/Qwen2.5-72B-Instruct-128K", 
         image_server="siliconflow", image_model="black-forest-labs/FLUX.1-schnell", 
         tts_server = "openai", voice="alloy", 
         generate_video = False, output_dir=None):
    
    try:
        # Input validation
        if not isinstance(content, str) or len(content) < 1000:
            raise ValueError("Content must be a string with at least 1000 characters")
        if not 1 < num_plots <= 20:
            raise ValueError("num_plots must be between 2 and 20")
        if not 0 <= num_images <= 5:
            raise ValueError("num_images must be between 0 and 5")
        if llm_server not in ["openai", "siliconflow"]:
            raise ValueError("llm_server must be either 'openai' or 'siliconflow'")
        if image_server not in ["openai", "siliconflow"]:
            raise ValueError("image_server must be either 'openai' or 'siliconflow'")
        if tts_server not in ["openai", "azure"]:
            raise ValueError("image_server must be either 'openai' or 'azure'")

        # Create folders
        base_dir = output_dir or os.path.expanduser("~/Desktop")
        visualization_folder = os.path.join(base_dir, "Content Visualization")
        images_folder = os.path.join(visualization_folder, "Images")
        audio_folder = os.path.join(visualization_folder, "Audio")
        video_folder = os.path.join(visualization_folder, "Video")
        os.makedirs(images_folder, exist_ok=True)
        os.makedirs(audio_folder, exist_ok=True)
        os.makedirs(video_folder, exist_ok=True)
        
        # Process content
        parsed_content = content_parser(llm_server, llm_model, content, num_plots)
        if not parsed_content:
            raise ValueError("Failed to parse content")
        parsed_saver(parsed_content, visualization_folder)
        
        # Generate images and prompts
        image_paths, prompt_file = generate_and_save_images(
            image_server, image_model, llm_server, llm_model,
            parsed_content, num_plots, num_images, image_size, images_folder
        )
        
        # Prepare images for video
        selected_images = []
        if generate_video == True:
            selected_images = prepare_images_for_video(images_folder, num_plots, num_images)
            if not selected_images:
                raise ValueError("Failed to prepare images for video")
        
        # Generate audio and create video for each plot
        media_path = create_media(parsed_content, audio_paths = audio_folder, image_paths = selected_images, video_paths = video_folder, 
                                              generate_video=generate_video, server=tts_server, voice=voice)

        return {
            "parsed_content": parsed_content,
            "images": image_paths,
            "image_prompts": prompt_file,
            "final_video": media_path
        }
    
    except ValueError as ve:
        print(f"Input error: {str(ve)}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    return None

# Run the main function
if __name__ == "__main__":
    
    result = main(content, num_plots=5, 
                  num_images=1,
                  image_size="1024x576", 
                  llm_server="openai",
                  llm_model="gpt-4o",
                  image_server="siliconflow",
                  image_model="black-forest-labs/FLUX.1-schnell", 
                  tts_server="openai",
                  voice="echo", 
                  generate_video=False,
                  output_dir=None)
    
    if result:
        if result["final_video"]:
            print("Hooray! The AIGC task was completed successfully with full content video creation!")
        elif result["images"]:
            print("The AIGC task was completed with images, but video generation failed.")
        else:
            print("The AIGC task was completed, but no media was generated.")
    else:
        print("The task could not be completed due to an error.")