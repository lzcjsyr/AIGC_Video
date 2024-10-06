import requests, json, re, os
from PIL import Image
from io import BytesIO
import azure.cognitiveservices.speech as speechsdk
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from input_text_en import (
    AZURE_SPEECH_KEY, 
    AZURE_SPEECH_REGION,
    SILICONFLOW_KEY,
    summarize_story_system_prompt, 
    plot_splitter_system_prompt,
    generate_image_system_prompt,
    AZURE_OPENAI_ENDPOINT, 
    AZURE_OPENAI_KEY, story
)

################ Story Summarization ################
def summarize_story(client, story):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.1,
            max_tokens=4000,
            messages=[
                {"role": "system", "content": summarize_story_system_prompt},
                {"role": "user", "content": f"Please summarize this story:\n\n{story}"}
            ]
        )
        
        content = response.choices[0].message.content
        json_str = content[content.find('{'):content.rfind('}')+1]
        json_str = re.sub(r'(?<=summary": ")(.|\n)*?(?=")', lambda m: m.group().replace('\n', '\\n'), json_str)
        
        print("Generated summary.")
        return json.loads(json_str)
    
    except (AttributeError, IndexError, json.JSONDecodeError) as e:
        print(f"Error processing story: {e}")
        return None

def plot_splitter(client, story, num_plots):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.1,
            max_tokens=4000,
            messages=[
                {"role": "system", "content": plot_splitter_system_prompt},
                {"role": "user", "content": f"Please split this story into {num_plots} distinct plot points:\n\n{story}"}
            ]
        )
        
        content = response.choices[0].message.content
        json_str = content[content.find('{'):content.rfind('}')+1]
        
        # Escape newlines within all string values in the JSON
        json_str = re.sub(r'": "(.|\n)*?"', lambda m: m.group().replace('\n', '\\n'), json_str)
        
        print("Generated plots.")
        return json.loads(json_str)
    
    except (AttributeError, IndexError, json.JSONDecodeError) as e:
        print(f"Error processing plot points: {e}")
        return None

def write_summary_and_plots(folder_path, summary_json, plots_json):
    with open(os.path.join(folder_path, "summary & plots.txt"), 'w', encoding='utf-8') as f:
        f.write(f"Title: {summary_json['title']}\n\n")
        f.write("Main Themes:\n" + "\n".join(f"- {theme}" for theme in summary_json['main_themes']) + "\n\n")
        f.write(f"Story Summary:\n{summary_json['summary']}\n\n")
        f.write("Plot Descriptions:\n" + "\n".join(f"\nPlot {i}:\n{plot['plot_description']}" 
                for i, plot in enumerate(plots_json['plots'], 1)))
    print("Saved summary and plots.")

################ Image Generation ################
def generate_image_prompt(client, plot, regenerate=False):

    system_message = generate_image_system_prompt
    if regenerate:
        system_message += """Create a safe, non-controversial prompt that captures the essence of the scene."""

    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.3,
        max_tokens=300,
        messages=[{"role": "system", "content": system_message},
                  {"role": "user", "content": f"Please consider all information and generate a detailed image prompt for DALL-E 3. \n\n{plot}"}]
    )

    return response.choices[0].message.content.strip()

def image_API(client, model_type, prompt):

    if model_type == "OpenAI":

        response = client.images.generate(model="dall-e-3", prompt=prompt, n=1, quality="hd", style="vivid", size="1792x1024")
        return(response.data[0].url)
    
    if model_type == "FLUX":

        url = "https://api.siliconflow.cn/v1/image/generations"
        headers = {"Authorization": f"Bearer {SILICONFLOW_KEY}", "Content-Type": "application/json"}
        payload = {"model": "Pro/black-forest-labs/FLUX.1-schnell", "prompt": prompt, "image_size": "1024x576"}
        
        response = requests.request("POST", url, json=payload, headers=headers)
        return(json.loads(response.text)["images"][0]['url'])
        
def generate_and_save_images(client, plots_json, plot_index, num_images, images_folder, model_type):
    # Validate plot index
    if not 0 < plot_index <= len(plots_json['plots']):
        print("Plot index is out of range.")
        return None, None

    plot = plots_json['plots'][plot_index-1]
    images = []
    image_prompt = generate_image_prompt(client, plot=plot)

    # Generate the specified number of images
    for _ in range(num_images):
        # Allow up to 5 attempts per image
        for attempt in range(5):
            try:
                # Generate image using the specified API
                image_url = image_API(client, model_type=model_type, prompt=image_prompt)
                image_response = requests.get(image_url)
                image = Image.open(BytesIO(image_response.content))
                images.append(image)
                print(f"Generated image {len(images)} for Plot {plot_index} using {model_type}.")
                break  # Success, move to next image
            except Exception as e:
                # Handle content policy violations by regenerating the prompt
                if 'content_policy_violation' in str(e) and attempt < 4:
                    print(f"Content policy violation. Regenerating prompt (Attempt {attempt+1})")
                    image_prompt = generate_image_prompt(client, plot=plot, regenerate=True)
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

################ Text to Speech ################
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
    
################ Video Creation ################
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