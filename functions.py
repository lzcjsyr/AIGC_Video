import requests, json, re, os
from typing import Optional, Dict, Any
from PIL import Image
from io import BytesIO
from docx import Document
import azure.cognitiveservices.speech as speechsdk
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip
from input_text_en import (
    AZURE_SPEECH_KEY, 
    AZURE_SPEECH_REGION,
    SILICONFLOW_KEY,
    story_parser_system_prompt,
    generate_image_system_prompt,
    AZURE_OPENAI_ENDPOINT, 
    AZURE_OPENAI_KEY, story
)

################ Story Parser ################
def story_parser(client, story: str, num_plots: int) -> Optional[Dict[str, Any]]:
    try:
        # Construct the user message with the number of plots
        user_message = f"Parse this story into {num_plots} plots, ensuring each plot is between 350 to 450 words:\n\n{story}"

        # Make the API call
        response = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.5,
            max_tokens=4096,
            messages=[{"role": "system", "content": story_parser_system_prompt},
                      {"role": "user", "content": user_message}]
        )
        
        # Extract and parse the JSON content
        content = response.choices[0].message.content
        json_str = content[content.find('{'):content.rfind('}')+1]
        output = json.loads(json_str)
        
        # Validate the output structure
        required_keys = ["title", "story_elements", "key_characters", "Segmentation"]
        if all(key in output for key in required_keys):
            print("Successfully generated and parsed story summary.")
            return output
        else:
            print("Error: Generated JSON does not match expected structure.")
            return None
    
    except json.JSONDecodeError:
        print("Error: Failed to parse JSON output.")
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
def generate_image_prompt(client, input, regenerate=False):
    # Define system message for image prompt generation
    system_message = generate_image_system_prompt
    if regenerate:
        system_message += "\n\nCreate a safe, non-controversial prompt that captures the essence of the scene."
    
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.5,
        max_tokens=500,
        messages=[{"role": "system", "content": system_message},
                  {"role": "user", "content": f"Generate an image prompt based on:\n{input}"}]
    )
    
    return response.choices[0].message.content

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

def generate_images(client, parsed_story, plot_index, num_images=1, saving_path=None, model_type="FLUX"):
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
    image_prompt = generate_image_prompt(client, input_for_prompt)

    images = []
    # Generate images
    for i in range(num_images):
        for attempt in range(5):
            try:
                image_url = image_API(client, model_type=model_type, prompt=image_prompt)
                image = Image.open(BytesIO(requests.get(image_url).content))
                images.append(image)
                print(f"Generated image {i+1} for Plot {plot_index} using {model_type}.")
                break
            except Exception as e:
                if 'content_policy_violation' in str(e) and attempt < 4:
                    print(f"Content policy violation. Regenerating prompt (Attempt {attempt+1})")
                    image_prompt = generate_image_prompt(client, input_for_prompt, regenerate=True)
                else:
                    print(f"Failed to generate image: {e}")
                    break

    # Save generated images
    image_paths = []
    for j, image in enumerate(images, 1):
        image_path = os.path.join(saving_path, f"plot_{plot_index}_image_{j}_{model_type}.png")
        image.save(image_path)
        image_paths.append(image_path)
    
    print(f"Saved {len(image_paths)} images for Plot {plot_index}.")
    return image_paths, image_prompt

def save_image_prompts(prompts, output_dir):
    doc = Document()
    doc.add_heading('Image Prompts', 0)
    for i, prompt in enumerate(prompts, 1):
        doc.add_heading(f'Plot {i}', level=1)
        doc.add_paragraph(prompt)
    prompt_file = os.path.join(output_dir, 'image_prompts.docx')
    doc.save(prompt_file)
    return prompt_file

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

# Function to ensure we have the correct number of images
def prepare_images_for_video(image_paths, num_plots):
    if len(image_paths) < num_plots:
        # If we have fewer images than plots, repeat the last image
        last_image = image_paths[-1] if image_paths else None
        image_paths.extend([last_image] * (num_plots - len(image_paths)))
    elif len(image_paths) > num_plots:
        # If we have more images than plots, take only the first image of each plot
        image_paths = image_paths[:num_plots]
    return image_paths