import os
from functions import (
    story_parser, parsed_saver, generate_and_save_images, 
    prepare_images_for_video, create_story_video, story
)

def main(story, num_plots=5, num_images=1,image_size="1024x1024",
         llm_server="siliconflow", llm_model="Qwen/Qwen2.5-72B-Instruct-128K", 
         image_server="siliconflow", image_model="black-forest-labs/FLUX.1-schnell", 
         voice_name="en-US-JennyNeural", output_dir=None):
    
    try:
        # Input validation
        if not isinstance(story, str) or len(story) < 1000:
            raise ValueError("Story must be a string with at least 1000 characters")
        if not 1 < num_plots <= 20:
            raise ValueError("num_plots must be between 2 and 20")
        if not 0 <= num_images <= 5:
            raise ValueError("num_images must be between 0 and 5")
        if llm_server not in ["azure", "siliconflow"]:
            raise ValueError("llm_server must be either 'azure' or 'siliconflow'")
        if image_server not in ["azure", "siliconflow"]:
            raise ValueError("image_server must be either 'azure' or 'siliconflow'")

        # Create folders
        base_dir = output_dir or os.path.expanduser("~/Desktop")
        visualization_folder = os.path.join(base_dir, "Story Visualization")
        images_folder = os.path.join(visualization_folder, "Images")
        audio_folder = os.path.join(visualization_folder, "Audio")
        video_folder = os.path.join(visualization_folder, "Video")
        os.makedirs(images_folder, exist_ok=True)
        os.makedirs(audio_folder, exist_ok=True)
        os.makedirs(video_folder, exist_ok=True)
        
        # Process story
        parsed_story = story_parser(llm_server, llm_model, story, num_plots)
        if not parsed_story:
            raise ValueError("Failed to parse story")
        parsed_saver(parsed_story, visualization_folder)
        
        # Generate images and prompts
        image_paths, prompt_file = generate_and_save_images(
            image_server, image_model, llm_server, llm_model,
            parsed_story, num_plots, num_images, image_size, images_folder
        )
        
        # Prepare images for video
        selected_images = prepare_images_for_video(images_folder, num_plots, num_images)
        if not selected_images:
            raise ValueError("Failed to prepare images for video")
        
        # Generate audio and create video for each plot
        final_video_path = create_story_video(parsed_story, selected_images, audio_folder, video_folder, voice_name)

        return {
            "parsed_story": parsed_story,
            "images": image_paths,
            "image_prompts": prompt_file,
            "final_video": final_video_path
        }
    
    except ValueError as ve:
        print(f"Input error: {str(ve)}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    return None

if __name__ == "__main__":
    result = main(story, num_plots=5, num_images=1, image_size="1024x1024",
                  llm_server="azure", llm_model="gpt-4o", 
                  image_server="siliconflow", image_model="black-forest-labs/FLUX.1-schnell", 
                  voice_name="en-US-JennyNeural", output_dir=None)
    if result:
        if result["final_video"]:
            print("Hooray! The AIGC task was completed successfully with full story video creation!")
        elif result["images"]:
            print("The AIGC task was completed with images, but video generation failed.")
        else:
            print("The AIGC task was completed, but no media was generated.")
    else:
        print("The task could not be completed due to an error.")