import os
import requests
from PIL import Image
from io import BytesIO
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from langchain_openai import AzureChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.tools import BaseTool
from typing import Dict, Any, List, Optional
import azure.cognitiveservices.speech as speechsdk

from input_text_en import (
    AZURE_SPEECH_KEY,
    AZURE_SPEECH_REGION,
    SILICONFLOW_KEY,
    summarize_story_system_prompt,
    plot_splitter_system_prompt,
    generate_image_system_prompt,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_KEY,
    story
)

os.environ["AZURE_OPENAI_API_KEY"] = AZURE_OPENAI_KEY
os.environ["AZURE_OPENAI_ENDPOINT"] = AZURE_OPENAI_ENDPOINT

# Initialize Azure ChatOpenAI
llm = AzureChatOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    azure_deployment="gpt-4o",
    openai_api_version="2024-06-01",
    temperature=0.3,
    max_tokens=4000
)

# Create LLMChains for text generation tasks
summarize_chain = LLMChain(
    llm=llm,
    prompt=PromptTemplate(
        input_variables=["story"],
        template=summarize_story_system_prompt + "\n\nPlease summarize this story:\n\n{story}"
    )
)

plot_splitter_chain = LLMChain(
    llm=llm,
    prompt=PromptTemplate(
        input_variables=["story", "num_plots"],
        template=plot_splitter_system_prompt + "\n\nPlease split this story into {num_plots} distinct plot points:\n\n{story}"
    )
)

image_prompt_chain = LLMChain(
    llm=llm,
    prompt=PromptTemplate(
        input_variables=["plot", "regenerate"],
        template=generate_image_system_prompt + "\n\n{regenerate}\n\nPlease consider all information and generate a detailed image prompt for DALL-E 3.\n\n{plot}"
    )
)

# Custom tool for image generation
class ImageGenerationTool(BaseTool):
    name: str = "image_generation"
    description: str = "Generate images based on a prompt"

    def _run(self, prompt: str, model_type: str) -> str:
        if model_type == "OpenAI":
            response = llm.client.images.generate(model="dall-e-3", prompt=prompt, n=1, quality="hd", style="vivid", size="1792x1024")
            return response.data[0].url
        elif model_type == "FLUX":
            url = "https://api.siliconflow.cn/v1/image/generations"
            headers = {"Authorization": f"Bearer {SILICONFLOW_KEY}", "Content-Type": "application/json"}
            payload = {"model": "Pro/black-forest-labs/FLUX.1-schnell", "prompt": prompt, "image_size": "1024x576"}
            response = requests.post(url, json=payload, headers=headers)
            return response.json()["images"][0]['url']
        else:
            raise ValueError("Invalid model_type. Choose 'OpenAI' or 'FLUX'.")

    async def _arun(self, prompt: str, model_type: str) -> str:
        # Async implementation if needed
        return self._run(prompt, model_type)

image_gen_tool = ImageGenerationTool()

# Custom function for text-to-speech using Azure
def text_to_speech(text: str, output_path: str, voice_name: str = "en-US-JennyNeural") -> Optional[str]:
    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    speech_config.speech_synthesis_voice_name = voice_name

    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    speech_synthesis_result = speech_synthesizer.speak_text_async(text).get()

    if speech_synthesis_result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("Speech synthesized for text [{}], and the audio was saved to [{}]".format(text, output_path))
        return output_path
    elif speech_synthesis_result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = speech_synthesis_result.cancellation_details
        print("Speech synthesis canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print("Error details: {}".format(cancellation_details.error_details))
        return None

def create_video(audio_path: str, image_paths: List[str], output_path: str) -> Optional[str]:
    try:
        audio = AudioFileClip(audio_path)
        duration = audio.duration
        image_duration = duration / len(image_paths)
        image_clips = [ImageClip(img_path).set_duration(image_duration) for img_path in image_paths]
        video = concatenate_videoclips(image_clips, method="compose").set_audio(audio)
        video.write_videofile(output_path, fps=24)
        return output_path
    except Exception as e:
        print(f"Error in video creation: {str(e)}")
        return None

def prepare_images_for_video(image_paths: List[str], num_plots: int) -> List[str]:
    if len(image_paths) < num_plots:
        last_image = image_paths[-1] if image_paths else None
        image_paths.extend([last_image] * (num_plots - len(image_paths)))
    return image_paths[:num_plots]

def write_summary_and_plots(folder_path: str, summary_json: Dict[str, Any], plots_json: Dict[str, Any]) -> None:
    with open(os.path.join(folder_path, "summary & plots.txt"), 'w', encoding='utf-8') as f:
        f.write(f"Title: {summary_json['title']}\n\n")
        f.write("Main Themes:\n" + "\n".join(f"- {theme}" for theme in summary_json['main_themes']) + "\n\n")
        f.write(f"Story Summary:\n{summary_json['summary']}\n\n")
        f.write("Plot Descriptions:\n" + "\n".join(f"\nPlot {i}:\n{plot['plot_description']}" 
                for i, plot in enumerate(plots_json['plots'], 1)))
    print("Saved summary and plots.")