import os
import json
import requests
from PIL import Image
from io import BytesIO
from typing import Dict, Any, Optional
from functions import (
    summarize_chain, plot_splitter_chain, image_prompt_chain, image_gen_tool,
    text_to_speech, create_video, prepare_images_for_video, write_summary_and_plots
)

def main(story: str, model_type: str = "FLUX", num_plots: int = 5, num_images: int = 1, output_dir: Optional[str] = None, voice_name: str = "en-US-JennyNeural") -> Dict[str, Any]:
    try:
        # Input validation
        if len(story) < 1000:
            raise ValueError("Story must have at least 1000 characters")
        if not 1 < num_plots <= 20:
            raise ValueError("num_plots must be between 2 and 20")
        if not 0 <= num_images <= 5:
            raise ValueError("num_images must be between 0 and 5")
        if model_type not in ["FLUX", "OpenAI"]:
            raise ValueError("model_type must be either 'FLUX' or 'OpenAI'")

        # Create folders
        base_dir = output_dir or os.path.expanduser("~/Desktop")
        visualization_folder = os.path.join(base_dir, "Story Visualization")
        images_folder = os.path.join(visualization_folder, "Images")
        os.makedirs(images_folder, exist_ok=True)

        # Process story
        summary_json = json.loads(summarize_chain.run(story))
        plots_json = json.loads(plot_splitter_chain.run(story=story, num_plots=num_plots))
        write_summary_and_plots(visualization_folder, summary_json, plots_json)

        # Generate images and prompts
        image_paths = []
        if num_images > 0:
            for i, plot in enumerate(plots_json['plots']):
                image_prompt = image_prompt_chain.run(plot=plot['plot_description'], regenerate="")
                for _ in range(num_images):
                    try:
                        image_url = image_gen_tool.run(prompt=image_prompt, model_type=model_type)
                        image_response = requests.get(image_url)
                        image = Image.open(BytesIO(image_response.content))
                        image_path = os.path.join(images_folder, f"plot_{i+1}_image_{_+1}_{model_type}.png")
                        image.save(image_path)
                        image_paths.append(image_path)
                    except Exception as e:
                        print(f"Failed to generate image: {e}")
                        if 'content_policy_violation' in str(e):
                            image_prompt = image_prompt_chain.run(plot=plot['plot_description'], regenerate="Create a safe, non-controversial prompt that captures the essence of the scene.")

        # Prepare images for video
        image_paths = prepare_images_for_video(image_paths, num_plots)

        # Generate audio
        audio_path = None
        if voice_name:
            audio_path = os.path.join(visualization_folder, "story_summary.wav")
            audio_path = text_to_speech(summary_json['summary'], audio_path, voice_name)

        # Create video
        video_path = None
        if audio_path and image_paths:
            video_path = os.path.join(visualization_folder, "story_video.mp4")
            video_path = create_video(audio_path, image_paths, video_path)

        return {
            "summary": summary_json,
            "plots": plots_json,
            "images": image_paths,
            "audio": audio_path,
            "video": video_path
        }

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

if __name__ == "__main__":
    from input_text_en import story
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