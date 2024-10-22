import os, requests
from openai import OpenAI
from dotenv import load_dotenv
from requests.exceptions import RequestException
import azure.cognitiveservices.speech as speechsdk

# Azure credentials and endpoints
load_dotenv()
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_SPEECH_KEY = os.getenv('AZURE_SPEECH_KEY')
AZURE_SPEECH_REGION = os.getenv('AZURE_SPEECH_REGION')
SILICONFLOW_KEY = os.getenv('SILICONFLOW_KEY')
AIPROXY_API_KEY = os.getenv('AIPROXY_API_KEY')
AIPROXY_URL = os.getenv('AIPROXY_URL')

# Validate environment variables
if not all([AZURE_OPENAI_ENDPOINT, AZURE_SPEECH_KEY, AZURE_SPEECH_REGION, SILICONFLOW_KEY, AIPROXY_API_KEY, AIPROXY_URL]):
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

def text_to_text(server, model, prompt, system_message="", max_tokens=4000, temperature=0.7, output_format="text"):
    
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}
    ]
    
    # Create OpenAI client
    if server == "openai":
        client = OpenAI(api_key=AIPROXY_API_KEY, base_url=AIPROXY_URL)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    # Create SiliconFlow client
    elif server == "siliconflow":
        headers = {"Authorization": f"Bearer {SILICONFLOW_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False, "top_p": 0.7, "top_k": 50, "frequency_penalty": 0.5, "n": 1,
            "response_format": {"type": "json_object"}
        }
        response = requests.post("https://api.siliconflow.cn/v1/chat/completions", headers=headers, json=payload).json()
    else:
        raise ValueError("Invalid server. Use 'openai' or 'siliconflow'.")
    
    # Return the response content
    if output_format == "text":
        return response.choices[0].message.content if server == "openai" else response.get("choices", [{}])[0].get('message', {}).get('content')
    return response

def text_to_image(prompt, size, server="siliconflow", model="black-forest-labs/FLUX.1-schnell"):
    
    # Create OpenAI client
    if server == "openai":
        client = OpenAI(base_url=AIPROXY_URL, api_key=AIPROXY_API_KEY)
        response = client.images.generate(
            model=model, prompt=prompt, n=1, quality="hd", style="vivid", size=size
        )
        return response.data[0].url if response.data else None
    
    # Create SiliconFlow client
    elif server == "siliconflow":
        headers = {"Authorization": f"Bearer {SILICONFLOW_KEY}", "Content-Type": "application/json"}
        payload = {"model": model, "prompt": prompt, "image_size": size}
        response = make_api_request("https://api.siliconflow.cn/v1/image/generations", "POST", headers, payload)
        return response.get("images", [{}])[0].get('url')
    
    else:
        raise ValueError("Invalid server. Use 'openai' or 'siliconflow'.")

def text_to_audio(server, text, output_filename, voice):
    
    if server == "openai":
        try:
            client = OpenAI(base_url=AIPROXY_URL, api_key=AIPROXY_API_KEY)
            response = client.audio.speech.create(model="tts-1-hd", voice=voice, input=text)

            # Save the audio content to a file
            with open(output_filename, 'wb') as audio_file:
                audio_file.write(response.content)
            return output_filename
        
        except Exception as e:
            print(f"Error in OpenAI text-to-speech conversion: {str(e)}")
            return None
        
    elif server == "azure":
        try:
            # Set up Azure Speech SDK configuration
            speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
            speech_config.speech_synthesis_voice_name = voice
            audio_config = speechsdk.audio.AudioOutputConfig(filename=output_filename)
            
            # Create a speech synthesizer and perform the speech synthesis
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
            result = synthesizer.speak_text_async(text).get()
            
            # Check if the speech synthesis was successful
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                return output_filename
            else:
                raise Exception(f"Speech synthesis failed: {result.reason}")
        
        except Exception as e:
            print(f"Error in Azure text-to-speech conversion: {str(e)}")
            return None
    
    else:
        print(f"Unsupported server: {server}")
        return None