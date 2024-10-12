import os
from openai import AzureOpenAI
from functions import (
    story_parser, parsed_saver, generate_images_and_prompts, 
    prepare_images_for_video, create_story_video,
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, story
)

def main(story, model_type="FLUX", num_plots=5, num_images=1, output_dir=None, voice_name="en-US-JennyNeural"):
    try:
        # Input validation
        if not isinstance(story, str) or len(story) < 1000:
            raise ValueError("Story must be a string with at least 1000 characters")
        if not 1 < num_plots <= 20:
            raise ValueError("num_plots must be between 2 and 20")
        if not 0 <= num_images <= 5:
            raise ValueError("num_images must be between 0 and 5")
        if model_type not in ["FLUX", "OpenAI"]:
            raise ValueError("model_type must be either 'FLUX' or 'OpenAI'")

        client = AzureOpenAI(azure_endpoint=AZURE_OPENAI_ENDPOINT, api_key=AZURE_OPENAI_KEY, api_version="2024-09-01-preview")
        
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
        parsed_story = story_parser(client, story, num_plots)
        if not parsed_story:
            raise ValueError("Failed to parse story")
        parsed_saver(parsed_story, visualization_folder)
        
        # Generate images and prompts
        image_paths, prompt_file = generate_images_and_prompts(
            client, parsed_story, num_plots, num_images, images_folder, visualization_folder, model_type)
        
        # Prepare images for video
        image_paths = prepare_images_for_video(image_paths, num_plots)
        
        # Generate audio and create video for each plot
        final_video_path = create_story_video(parsed_story, image_paths, audio_folder, video_folder, voice_name)

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
    result = main(story, model_type="FLUX", num_plots=3, num_images=1, output_dir=None, voice_name="en-US-JennyNeural")
    if result:
        if result["final_video"]:
            print("Hooray! The AIGC task was completed successfully with full story video creation!")
        elif result["plot_videos"]:
            print("The AIGC task was completed with individual plot videos, but full video concatenation failed.")
        elif result["images"]:
            print("The AIGC task was completed with images, but video generation failed.")
        else:
            print("The AIGC task was completed, but no media was generated.")
    else:
        print("The task could not be completed due to an error.")