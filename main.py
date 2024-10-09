import os
from openai import AzureOpenAI
from functions import (
    summarize_story, plot_splitter, text_to_speech, write_summary_and_plots, 
    generate_and_save_images, create_video, prepare_images_for_video,
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

        client = AzureOpenAI(azure_endpoint=AZURE_OPENAI_ENDPOINT, api_key=AZURE_OPENAI_KEY, api_version="2024-06-01")
        
        # Create folders
        base_dir = output_dir or os.path.expanduser("~/Desktop")
        visualization_folder = os.path.join(base_dir, "Story Visualization")
        images_folder = os.path.join(visualization_folder, "Images")
        os.makedirs(images_folder, exist_ok=True)
        
        # Process story
        summary_json = summarize_story(client, story)
        if not summary_json:
            raise ValueError("Failed to generate summary")
        
        plots_json = plot_splitter(client, story, num_plots)
        if not plots_json:
            raise ValueError("Failed to split plot")
        
        write_summary_and_plots(visualization_folder, summary_json, plots_json)
        
        # Generate images and prompts
        image_paths = []
        if num_images > 0:
            results = [generate_and_save_images(client, plots_json=plots_json, plot_index=i+1, 
                                                num_images=num_images, images_folder=images_folder, 
                                                model_type=model_type) for i in range(len(plots_json['plots']))]
            image_paths = [path for result in results if result and result[0] for path in result[0]]
        else:
            print("Skipping image generation.")
        
        # Prepare images for video
        image_paths = prepare_images_for_video(image_paths, num_plots)
        
        # Generate audio
        audio_path = None
        if voice_name:
            audio_path = text_to_speech(summary_json['summary'], os.path.join(visualization_folder, "story_summary.wav"), voice_name)
            if not audio_path:
                print("Audio generation failed.")
        else:
            print("Skipping audio generation.")

        # Create video
        video_path = None
        if audio_path and image_paths:
            video_path = os.path.join(visualization_folder, "story_video.mp4")
            video_path = create_video(audio_path, image_paths, video_path)
            if video_path:
                print(f"Video created: {video_path}")
            else:
                print("Video creation failed.")
        else:
            print("Skipping video creation due to missing audio or images.")

        return {
            "summary": summary_json, 
            "images": image_paths, 
            "audio": audio_path,
            "video": video_path
        }
    
    except ValueError as ve:
        print(f"Input error: {str(ve)}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    return None

if __name__ == "__main__":
    result = main(story, model_type="OpenAI", num_plots=5, num_images=1, output_dir=None, voice_name="en-US-AvaMultilingualNeural")
    if result:
        if result["video"]:
            print("Hooray! The AIGC task was completed successfully with video creation!")
        elif result["audio"]:
            print("The AIGC task was completed with audio, but video creation failed.")
        elif result["images"]:
            print("The AIGC task was completed with images, but audio and video generation failed.")
        else:
            print("The AIGC task was completed, but no media was generated.")
    else:
        print("The task could not be completed due to an error.")