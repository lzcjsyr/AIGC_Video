import os
from openai import AzureOpenAI
from docx import Document
from functions import (
    story_parser, parsed_saver, generate_images, text_to_speech,
    create_video, prepare_images_for_video, save_image_prompts,
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
        image_paths = []
        image_prompts = []
        if num_images > 0:
            for i in range(num_plots):
                plot_images, prompt = generate_images(client, parsed_story, i+1, num_images, images_folder, model_type)
                image_paths.extend(plot_images)
                image_prompts.append(prompt)
            
            # Save image prompts to a single docx file
            prompt_file = save_image_prompts(image_prompts, visualization_folder)
            print(f"Image prompts saved to: {prompt_file}")
        else:
            print("Skipping image generation.")
        
        # Prepare images for video
        image_paths = prepare_images_for_video(image_paths, num_plots)
        
        # Generate audio and create video for each plot
        plot_videos = []
        for i, plot in enumerate(parsed_story['Segmentation']):
            audio_path = text_to_speech(plot['plot'], os.path.join(audio_folder, f"plot_{i+1}.wav"), voice_name)
            if not audio_path:
                print(f"Audio generation failed for plot {i+1}.")
                continue
            
            plot_image_paths = image_paths[i:i+1]  # Use one image per plot
            plot_video_path = os.path.join(video_folder, f"plot_{i+1}.mp4")
            plot_video_path = create_video(audio_path, plot_image_paths[0], plot_video_path)
            if plot_video_path:
                plot_videos.append(plot_video_path)
                print(f"Video created for plot {i+1}: {plot_video_path}")
            else:
                print(f"Video creation failed for plot {i+1}.")
        
        # Concatenate all plot videos
        final_video_path = os.path.join(visualization_folder, "full_story_video.mp4")
        if plot_videos:
            from moviepy.editor import concatenate_videoclips, VideoFileClip
            clips = [VideoFileClip(video) for video in plot_videos]
            final_video = concatenate_videoclips(clips)
            final_video.write_videofile(final_video_path)
            print(f"Full story video created: {final_video_path}")
        else:
            print("Failed to create full story video due to missing plot videos.")

        return {
            "parsed_story": parsed_story,
            "images": image_paths,
            "image_prompts": prompt_file,
            "plot_videos": plot_videos,
            "final_video": final_video_path if plot_videos else None
        }
    
    except ValueError as ve:
        print(f"Input error: {str(ve)}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    return None

if __name__ == "__main__":
    result = main(story, model_type="FLUX", num_plots=5, num_images=1, output_dir=None, voice_name="en-US-JennyNeural")
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