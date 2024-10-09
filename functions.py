import requests
import json
import os
from PIL import Image
from io import BytesIO
import azure.cognitiveservices.speech as speechsdk
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
AZURE_SPEECH_KEY = os.getenv('AZURE_SPEECH_KEY')
AZURE_SPEECH_REGION = os.getenv('AZURE_SPEECH_REGION')
SILICONFLOW_KEY = os.getenv('SILICONFLOW_KEY')

def write_summary_and_plots(folder_path, summary, plots):
    with open(os.path.join(folder_path, "summary & plots.txt"), 'w', encoding='utf-8') as f:
        f.write(f"Title: {summary.title}\n\n")
        f.write("Main Themes:\n" + "\n".join(f"- {theme}" for theme in summary.main_themes) + "\n\n")
        f.write(f"Story Summary:\n{summary.summary}\n\n")
        f.write("Plot Descriptions:\n" + "\n".join(f"\nPlot {plot.num_plot}:\n{plot.plot_description}" 
                for plot in plots.plots))
    print("Saved summary and plots.")

def generate_image_prompt(llm, plot, regenerate=False):
    system_message = """
    Generate single-scene prompts with these elements:

    Image Style: Photorealistic, high-detail, epic composition, vivid colors, elegant features.
    Characters: Specify age, gender, body type, hairstyle, and traditional Chinese attire.
    Setting: Ancient China (exact period), authentic architecture, props, and landscapes.
    Mood: Use dramatic lighting and atmosphere to enhance the scene's emotion.

    Avoid: Modern elements, abstract styles, text overlays.
    Output: Provide only the generated prompt, no explanations.
    """
    
    if regenerate:
        system_message += """Create a safe, non-controversial prompt that captures the essence of the scene."""

    prompt_template = PromptTemplate(
        input_variables=["system_message", "plot"],
        template="{system_message}\n\nPlease consider all information and generate a detailed image prompt for DALL-E 3. \n\n{plot}"
    )
    
    chain = LLMChain(llm=llm, prompt=prompt_template)
    return chain.run(system_message=system_message, plot=plot)

def image_API(model_type, prompt):
    if model_type == "OpenAI":
        # Note: This part needs to be updated to use the OpenAI API directly,
        # as LangChain doesn't provide direct image generation capabilities.
        # You may need to use the OpenAI Python client here.
        pass
    
    if model_type == "FLUX":
        url = "https://api.siliconflow.cn/v1/image/generations"
        headers = {"Authorization": f"Bearer {SILICONFLOW_KEY}", "Content-Type": "application/json"}
        payload = {"model": "Pro/black-forest-labs/FLUX.1-schnell", "prompt": prompt, "image_size": "1024x576"}
        
        response = requests.request("POST", url, json=payload, headers=headers)
        return json.loads(response.text)["images"][0]['url']

def generate_and_save_images(llm, plots_json, plot_index, num_images, images_folder, model_type):
    # Validate plot index
    if not 0 < plot_index <= len(plots_json['plots']):
        print("Plot index is out of range.")
        return None, None

    plot = plots_json['plots'][plot_index-1]
    images = []
    image_prompt = generate_image_prompt(llm, plot=json.dumps(plot))

    # Generate the specified number of images
    for _ in range(num_images):
        # Allow up to 5 attempts per image
        for attempt in range(5):
            try:
                # Generate image using the specified API
                image_url = image_API(model_type=model_type, prompt=image_prompt)
                image_response = requests.get(image_url)
                image = Image.open(BytesIO(image_response.content))
                images.append(image)
                print(f"Generated image {len(images)} for Plot {plot_index} using {model_type}.")
                break  # Success, move to next image
            except Exception as e:
                # Handle content policy violations by regenerating the prompt
                if 'content_policy_violation' in str(e) and attempt < 4:
                    print(f"Content policy violation. Regenerating prompt (Attempt {attempt+1})")
                    image_prompt = generate_image_prompt(llm, plot=json.dumps(plot), regenerate=True)
                else:
                    print(f"Failed to generate image: {e}")
                    break  # Move to next image on other errors

    # Save generated images
    image_paths = []
    for j, image in enumerate(images, 1):
        image_path = os.path.join(images_folder, f"plot_{plot_index}_image_{j}_{model_type}.png")
        image.save(image_path)
        image_paths.append(image_path)

    # Record the image prompt used
    with open(os.path.join(images_folder, "image_prompts.txt"), "a") as f:
        f.write(f"Plot {plot_index} Prompt:\n{image_prompt}\n\n")

    print(f"Saved {len(image_paths)} images and prompt for Plot {plot_index}.")
    return image_paths, image_prompt

def text_to_speech(text, output_filename="output.wav", voice_name="en-US-JennyNeural"):
    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    speech_config.speech_synthesis_voice_name = voice_name
    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_filename)
    
    try:
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        result = synthesizer.speak_text_async(text).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return output_filename
        else:
            raise Exception(f"Speech synthesis failed: {result.reason}")
    except Exception as e:
        print(f"Error in text-to-speech conversion: {str(e)}")
        return None

def create_video(audio_path, image_paths, output_path):
    # Load the audio file
    audio = AudioFileClip(audio_path)
    duration = audio.duration

    # Calculate the duration for each image
    image_duration = duration / len(image_paths)

    # Create image clips
    image_clips = [ImageClip(img_path).set_duration(image_duration) for img_path in image_paths]

    # Concatenate image clips
    video = concatenate_videoclips(image_clips, method="compose")

    # Set the audio of the video
    video = video.set_audio(audio)

    # Write the result to a file
    video.write_videofile(output_path, fps=24)

    return output_path