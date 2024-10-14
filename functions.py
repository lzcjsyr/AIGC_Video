import requests, json, os, re
from typing import Optional, Dict, Any
from PIL import Image
from io import BytesIO
from docx import Document
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips, VideoFileClip
from input_text_en import story_parser_system_prompt, generate_image_system_prompt, story
from gen_ai_api import text_to_text, text_to_image, text_to_audio

################ Story Parser ################
def story_parser(server: str, model: str, story: str, num_plots: int) -> Optional[Dict[str, Any]]:
    
    try:
        user_message = f"Parse this story into {num_plots} plots, ensuring each plot is between 350 to 450 words:\n\n{story}"

        # Call the text_to_text function to parse the content
        content = text_to_text(server=server, model=model, prompt=user_message, system_message=story_parser_system_prompt, max_tokens=4096, temperature=0.7)
        if content is None:
            raise ValueError("Failed to get response from API.")
        
        # Find the JSON part of the content
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON object found in the response.")
        else:
            output = json.loads(content[json_start:json_end])
        
        # Validate the output structure
        required_keys = ["title", "story_elements", "key_characters", "Segmentation"]
        if all(key in output for key in required_keys):
            print("Successfully generated and parsed story summary.")
            return output
        else:
            missing_keys = [key for key in required_keys if key not in output]
            raise ValueError(f"Generated JSON is missing required keys: {', '.join(missing_keys)}")
    
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON output. Error details: {str(e)}")
        print("Problematic JSON string:")
        print(output)
        return None
    except Exception as e:
        print(f"Error processing story: {str(e)}")
        return None

def parsed_saver(parsed_json, saving_path=None):
    doc = Document()
    
    # Set default path to desktop if no path is provided
    if saving_path is None:
        saving_path = os.path.join(os.path.expanduser("~"), "Desktop")
    
    # Title
    doc.add_heading(parsed_json['title'], 0)
    
    # Story Elements
    doc.add_heading('Story Elements', level=1)
    for element in parsed_json['story_elements']:
        doc.add_paragraph(element, style='List Bullet')
    
    # Key Characters
    doc.add_heading('Key Characters', level=1)
    for character in parsed_json['key_characters']:
        doc.add_paragraph(character['name'], style='Heading 3')
        for key, value in character.items():
            if key != 'name':
                if isinstance(value, list):
                    doc.add_paragraph(f"{key.capitalize()}: {', '.join(value)}")
                else:
                    doc.add_paragraph(f"{key.capitalize()}: {value}")
    
    # Segmentation
    doc.add_heading('Plot Segments', level=1)
    for i, segment in enumerate(parsed_json['Segmentation'], 1):
        doc.add_heading(f"Segment {i}", level=2)
        doc.add_paragraph(segment['plot'])
        doc.add_paragraph(f"Themes: {', '.join(segment['plot_theme'])}")
        doc.add_paragraph(f"Characters: {', '.join(segment['characters_name'])}")
    
    # Save the document
    doc_path = os.path.join(saving_path, f"{parsed_json['title']}.docx")
    doc.save(doc_path)
    print(f"Saved document to {doc_path}")

################ Image Generation ################
def generate_image_prompt(server, model, prompt, regenerate=False):
    
    # Define system message for image prompt generation
    system_message = generate_image_system_prompt
    if regenerate:
        system_message += "\n\nCreate a safe, non-controversial prompt that captures the essence of the scene."
    
    response = text_to_text(server = server, model = model, prompt = prompt, system_message = system_message, max_tokens=4096, temperature=0.7)
    return response.choices[0].message.content

def generate_images(image_server, image_model, llm_server, llm_model, parsed_story, plot_index, size, num_images=1, saving_path=None):
    
    if saving_path is None:
        saving_path = os.path.join(os.path.expanduser('~'), 'Desktop')
    if num_images < 1:
        print("Input of num_images is out of range.")
        return None, None
    
    # Extract plot and characters
    plot = parsed_story["Segmentation"][plot_index - 1]
    characters = [char for char in parsed_story["key_characters"] if char["name"] in plot["characters_name"]]
    
    # Generate image prompt
    input_for_prompt = f"Plot: {plot['plot']}\nCharacters: {characters}"
    image_prompt = generate_image_prompt(server = llm_server, model = llm_model, prompt = input_for_prompt, regenerate = False)

    images = []
    # Generate images
    for i in range(num_images):
        for attempt in range(5):
            try:
                image_url = text_to_image(server = image_server, model = image_model, prompt = image_prompt, size = size)
                image = Image.open(BytesIO(requests.get(image_url).content))
                images.append(image)
                print(f"Generated image {i+1} for Plot {plot_index} using {image_model}.")
                break
            except Exception as e:
                if 'content_policy_violation' in str(e) and attempt < 4:
                    print(f"Content policy violation. Regenerating prompt (Attempt {attempt+1})")
                    image_prompt = generate_image_prompt(server = llm_server, model = llm_model, prompt = input_for_prompt, regenerate = True)
                else:
                    print(f"Failed to generate image: {e}")
                    break

    # Save generated images
    image_paths = []
    for j, image in enumerate(images, 1):
        image_path = os.path.join(saving_path, f"plot_{plot_index}_image_{j}_{image_model}.png")
        image.save(image_path)
        image_paths.append(image_path)
    
    print(f"Saved {len(image_paths)} images for Plot {plot_index}.")
    return image_paths, image_prompt

def generate_and_save_images(image_server, image_model, llm_server, llm_model, parsed_story, num_plots, num_images, size, saving_path):
    image_paths = []
    image_prompts = []
    
    if num_images > 0:
        for i in range(num_plots):
            plot_images, prompt = generate_images(image_server, image_model, llm_server, llm_model, 
                                                  parsed_story, plot_index = i, size = size, num_images=1, saving_path=None)
            image_paths.extend(plot_images)
            image_prompts.append(prompt)
        
        # Save image prompts to a single docx file
        doc = Document()
        doc.add_heading('Image Prompts', 0)
        for i, prompt in enumerate(image_prompts, 1):
            doc.add_heading(f'Plot {i}', level=1)
            doc.add_paragraph(prompt)
        prompt_file = os.path.join(saving_path, 'image_prompts.docx')
        doc.save(prompt_file)
        print(f"Image prompts saved to: {prompt_file}")
    else:
        print("Skipping image generation.")
        prompt_file = None
    
    return image_paths, prompt_file

################ Audio and Video ################
def prepare_images_for_video(images_folder, num_plots, num_images):
    # Check if the image folder exists
    if not os.path.exists(images_folder):
        print("Error: Image folder does not exist.")
        return None

    selected_images = []
    
    for plot in range(1, num_plots + 1):
        # Get all images for the current plot
        plot_images = [img for img in os.listdir(images_folder) if f"plot_{plot}_" in img]
        
        # Check if the number of images matches the generation requirements
        if len(plot_images) != num_images:
            print(f"Error: Expected {num_images} images for plot {plot}, but found {len(plot_images)}.")
            return None
        
        if num_images == 1:
            # If only one image per plot, select it automatically
            if not plot_images:
                print(f"Error: No image found for plot {plot}.")
                return None
            selected_images.append(os.path.join(images_folder, plot_images[0]))
        else:
            # Ask user to select an image for this plot
            print(f"\nAvailable images for plot {plot}:")
            for i, img in enumerate(plot_images, 1):
                print(f"{i}. {img}")
            
            while True:
                try:
                    choice = int(input(f"Please select an image for plot {plot} (1-{len(plot_images)}): "))
                    if 1 <= choice <= len(plot_images):
                        selected_images.append(os.path.join(images_folder, plot_images[choice - 1]))
                        break
                    else:
                        print("Invalid selection. Please try again.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
    
    if len(selected_images) != num_plots:
        print(f"Error: Expected {num_plots} selected images, but got {len(selected_images)}.")
        return None
    
    return selected_images
    
def create_video(audio_path, image_path, output_path):
    try:
        # Load audio and image
        audio = AudioFileClip(audio_path)
        image = ImageClip(image_path).set_duration(audio.duration)

        # Create and save video
        video = CompositeVideoClip([image]).set_audio(audio)
        video.write_videofile(output_path, fps=24)

        return output_path
    
    except Exception as e:
        print(f"Error in video creation: {str(e)}")
        return None
    
def create_story_video(parsed_story, image_paths, audio_paths, video_paths, voice_name):
    
    plot_videos = []
    for i, plot in enumerate(parsed_story['Segmentation']):
        audio_path = text_to_audio(plot['plot'], os.path.join(audio_paths, f"plot_{i+1}.wav"), voice_name)
        if not audio_path:
            print(f"Audio generation failed for plot {i+1}.")
            continue
        
        plot_image_paths = image_paths[i:i+1]  # Use one image per plot
        plot_video_path = os.path.join(video_paths, f"plot_{i+1}.mp4")
        plot_video_path = create_video(audio_path, plot_image_paths[0], plot_video_path)
        if plot_video_path:
            plot_videos.append(plot_video_path)
            print(f"Video created for plot {i+1}: {plot_video_path}")
        else:
            print(f"Video creation failed for plot {i+1}.")
    
    # Concatenate all plot videos
    final_video_path = os.path.join(video_paths, "full_story_video.mp4")
    if plot_videos:
        clips = [VideoFileClip(video) for video in plot_videos]
        final_video = concatenate_videoclips(clips)
        final_video.write_videofile(final_video_path)
        print(f"Full story video created: {final_video_path}")
        return final_video_path
    else:
        print("Failed to create full story video due to missing plot videos.")
        return None