import os, requests
from openai import AzureOpenAI
from dotenv import load_dotenv
from requests.exceptions import RequestException
import azure.cognitiveservices.speech as speechsdk

# Azure credentials and endpoints
load_dotenv()
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_KEY = os.getenv('AZURE_OPENAI_KEY')
AZURE_SPEECH_KEY = os.getenv('AZURE_SPEECH_KEY')
AZURE_SPEECH_REGION = os.getenv('AZURE_SPEECH_REGION')
SILICONFLOW_KEY = os.getenv('SILICONFLOW_KEY')

# Validate environment variables
if not all([AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_SPEECH_KEY, AZURE_SPEECH_REGION]):
    raise ValueError("Missing required Azure credentials in .env file.")

def make_api_request(api_url, method, headers, payload=None):
    try:
        # Make the API request using the requests library
        response = requests.request(method, api_url, json=payload, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json() if response.content else {}
    except RequestException as e:
        print(f"API request failed: {e}")
        return {}

def text_to_text(server, model, prompt, system_message="None", max_tokens=4000, temperature=0.7):
    
    # Create Azure OpenAI client
    if server == "azure":
        
        client = AzureOpenAI(azure_endpoint=AZURE_OPENAI_ENDPOINT, api_key=AZURE_OPENAI_KEY, api_version="2024-09-01-preview")
        
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system_message},
                      {"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    # Create SiliconFlow client
    if server == "siliconflow":

        headers = {"Authorization": f"Bearer {SILICONFLOW_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system_message},
                         {"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False, "top_p": 0.7, "top_k": 50, "frequency_penalty": 0.5, "n": 1,
            "response_format": {"type": "json_object"}
        }
        
        response_json = make_api_request("https://api.siliconflow.cn/v1/chat/completions", "POST", headers, payload)
        
        return response_json.get("choices", [{}])[0].get('message', {}).get('content', None)
    
    else:
        raise ValueError("Invalid server specified. Please use either 'azure' or 'siliconflow'.")

def text_to_image(server, model, prompt, size):
    
    # Create Azure OpenAI client
    if server == "azure":
        
        client = AzureOpenAI(azure_endpoint=AZURE_OPENAI_ENDPOINT, api_key=AZURE_OPENAI_KEY, api_version="2024-09-01-preview")
        
        response = client.images.generate(model=model, prompt=prompt, n=1, quality="hd", style="vivid", size=size)
        return response.data[0].url if response.data else None

    # Create SiliconFlow client    
    if server == "siliconflow":

        headers = {"Authorization": f"Bearer {SILICONFLOW_KEY}", "Content-Type": "application/json"}
        payload = {"model": model, "prompt": prompt, "image_size": size}
        
        response = make_api_request("https://api.siliconflow.cn/v1/image/generations", "POST", headers, payload)
        return response.get("images", [{}])[0].get('url', None)
    
    else:
        raise ValueError("Invalid server specified. Please use either 'azure' or 'siliconflow'.")

def text_to_audio(text, output_filename="output.wav", voice_name="en-US-JennyNeural"):
    
    # Set up Azure Speech SDK configuration
    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    speech_config.speech_synthesis_voice_name = voice_name
    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_filename)
    
    try:
        # Create a speech synthesizer and perform the speech synthesis
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        result = synthesizer.speak_text_async(text).get()
        
        # Check if the speech synthesis was successful
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return output_filename
        else:
            raise Exception(f"Speech synthesis failed: {result.reason}")
    
    except Exception as e:
        print(f"Error in text-to-speech conversion: {str(e)}")
        return None