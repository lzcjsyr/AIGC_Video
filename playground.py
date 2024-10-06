import os
import azure.cognitiveservices.speech as speechsdk

AZURE_SPEECH_KEY = "3c9ac94d72594326a9bd9e3cee8fa0b4"
AZURE_SPEECH_REGION = "eastus"

# Set up the speech configuration
speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
speech_config.speech_synthesis_voice_name = "en-US-AvaNeural"

# Set up the audio output format
audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)

# Set up the synthesizer
synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

# Synthesize the audio and save it to a variable
result = synthesizer.speak_text_async("Hello, world!").get()
audio_data = result.audio_data

# Check the result
if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    print("Speech synthesized for text 'Hello, world!'")
elif result.reason == speechsdk.ResultReason.Canceled:
    cancellation_details = result.cancellation_details
    print("Speech synthesis canceled: {}".format(cancellation_details.reason))
    if cancellation_details.reason == speechsdk.CancellationReason.Error:
        print("Error details: {}".format(cancellation_details.error_details))

#############################
import unittest
from unittest.mock import patch, Mock
from MIT_all_in_one import conditional_llm

class TestConditionalLLM(unittest.TestCase):

    @patch('your_module.llm')
    def test_with_api_base(self, mock_llm):
        # Setup
        mock_decorated_func = Mock()
        mock_llm.return_value = lambda x: mock_decorated_func

        # Define a dummy function to decorate
        def dummy_func():
            pass

        # Apply the conditional_llm decorator
        decorated_func = conditional_llm(model="test_model", api_base="http://test_api_base")(dummy_func)

        # Assert
        mock_llm.assert_called_once_with(model="test_model", api_base="http://test_api_base")
        self.assertEqual(decorated_func, mock_decorated_func)

    @patch('your_module.llm')
    def test_without_api_base(self, mock_llm):
        # Setup
        mock_decorated_func = Mock()
        mock_llm.return_value = lambda x: mock_decorated_func

        # Define a dummy function to decorate
        def dummy_func():
            pass

        # Apply the conditional_llm decorator
        decorated_func = conditional_llm(model="test_model", api_key="test_api_key")(dummy_func)

        # Assert
        mock_llm.assert_called_once_with(model="test_model", api_key="test_api_key")
        self.assertEqual(decorated_func, mock_decorated_func)

    @patch('your_module.llm')
    def test_default_parameters(self, mock_llm):
        # Setup
        mock_decorated_func = Mock()
        mock_llm.return_value = lambda x: mock_decorated_func

        # Define a dummy function to decorate
        def dummy_func():
            pass

        # Apply the conditional_llm decorator with only the model parameter
        decorated_func = conditional_llm(model="test_model")(dummy_func)

        # Assert
        mock_llm.assert_called_once_with(model="test_model", api_key=None)
        self.assertEqual(decorated_func, mock_decorated_func)

if __name__ == '__main__':
    unittest.main()

#############################
def my_decorator(func):
    def wrapper():
        print("Something is happening before the function is called.")
        func()
        print("Something is happening after the function is called.")
    return wrapper

@my_decorator
def say_hello():
    print("Hello!")

say_hello()
#############################
import time

def timing_decorator(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} took {end_time - start_time:.2f} seconds to run.")
        return result
    return wrapper

@timing_decorator
def slow_function():
    time.sleep(2)
    print("Function complete")

slow_function()
#############################
from promptic import llm

model = "gpt-4o"
api_base = "https://openai-cody.openai.azure.com/"
api_key = "744f68ceda254bb7a82f4793499efedb"

# First, let's see what llm returns
decorator = llm(model=model, api_base=api_base)
print("Type of llm output:", type(decorator))
print("llm output:", decorator)

# Now, let's apply this decorator to a simple function
@llm(model=model, api_key=api_key, api_base=api_base)
def test_function():
    """
    This is a test function that returns a greeting.
    Please process the following text: Hello, world!
    """
    return "Hello, world!"

# Let's call the decorated function
result = test_function()
print("Result of decorated function:", result)

#############################
from openai import AzureOpenAI
from azure.core.exceptions import AzureError
from tenacity import retry, retry_if_exception_type
from pydantic import BaseModel
from typing import List, Literal
import json

INSTRUCTION_TEMPLATES = {
    "podcast": {
        "intro": """Your task is to take the input text provided and turn it into an lively, engaging, informative podcast dialogue, in the style of NPR. The input text may be messy or unstructured, as it could come from a variety of sources like PDFs or web pages. 

Don't worry about the formatting issues or any irrelevant information; your goal is to extract the key points, identify definitions, and interesting facts that could be discussed in a podcast. 

Define all terms used carefully for a broad audience of listeners.
""",
        "text_instructions": "First, carefully read through the input text and identify the main topics, key points, and any interesting facts or anecdotes. Think about how you could present this information in a fun, engaging way that would be suitable for a high quality presentation.",
        "scratch_pad": """Brainstorm creative ways to discuss the main topics and key points you identified in the input text. Consider using analogies, examples, storytelling techniques, or hypothetical scenarios to make the content more relatable and engaging for listeners.

Keep in mind that your podcast should be accessible to a general audience, so avoid using too much jargon or assuming prior knowledge of the topic. If necessary, think of ways to briefly explain any complex concepts in simple terms.

Use your imagination to fill in any gaps in the input text or to come up with thought-provoking questions that could be explored in the podcast. The goal is to create an informative and entertaining dialogue, so feel free to be creative in your approach.

Define all terms used clearly and spend effort to explain the background.

Write your brainstorming ideas and a rough outline for the podcast dialogue here. Be sure to note the key insights and takeaways you want to reiterate at the end.

Make sure to make it fun and exciting. 
""",
        "prelude": """Now that you have brainstormed ideas and created a rough outline, it's time to write the actual podcast dialogue. Aim for a natural, conversational flow between the host and any guest speakers. Incorporate the best ideas from your brainstorming session and make sure to explain any complex topics in an easy-to-understand way.
""",
        "dialog": """Write a very long, engaging, informative podcast dialogue here, based on the key points and creative ideas you came up with during the brainstorming session. Use a conversational tone and include any necessary context or explanations to make the content accessible to a general audience. 

Never use made-up names for the hosts and guests, but make it an engaging and immersive experience for listeners. Do not include any bracketed placeholders like [Host] or [Guest]. Design your output to be read aloud -- it will be directly converted into audio.

Make the dialogue as long and detailed as possible, while still staying on topic and maintaining an engaging flow. Aim to use your full output capacity to create the longest podcast episode you can, while still communicating the key information from the input text in an entertaining way.

At the end of the dialogue, have the host and guest speakers naturally summarize the main insights and takeaways from their discussion. This should flow organically from the conversation, reiterating the key points in a casual, conversational manner. Avoid making it sound like an obvious recap - the goal is to reinforce the central ideas one last time before signing off. 

The podcast should have around 20000 words.
"""}
}

Story = """
Title: THE MARRIAGE LOTTERY.
A certain labourer’s son, named Ma T‘ien-jung, lost his wife when he was only about twenty years of age, and was too poor to take another. 
One day when out hoeing in the fields, he beheld a nice-looking young lady leave the path and come tripping across the furrows towards him. 
Her face was well painted, and she had altogether such a refined look that Ma concluded she must have lost her way, and began to make some playful remarks in consequence. “You go along home,” cried the young lady, “and I’ll be with you by-and-by.” 
Ma doubted this rather extraordinary promise, but she vowed and declared she would not break her word; and then Ma went off, telling her that his front door faced the north, etc., etc. 
In the evening the young lady arrived, and then Ma saw that her hands and face were covered with fine hair, which made him suspect at once she was a fox. 
She did not deny the accusation; and accordingly Ma said to her, “If you really are one of those wonderful creatures you will be able to get me anything I want; and I should be much obliged if you would begin by giving me some money to relieve my poverty.” 
The young lady said she would; and next evening when she came again, Ma asked her where the money was. “Dear me!” replied she, “I quite forgot it.” When she was going away, Ma reminded her of what he wanted, but on the following evening she made precisely the same excuse, promising to bring it another day. 
A few nights afterwards Ma asked her once more for the money, and then she drew from her sleeve two pieces of silver, each weighing about five or six ounces. They were both of fine quality, with turned-up edges,[350] and Ma was very pleased and stored them away in a cupboard. 
Some months after this, he happened to require some money for use, and took out these pieces; but the person to whom he showed them said they were only pewter, and easily bit off a portion of one of them with his teeth. Ma was much alarmed, and put the pieces away directly; taking the opportunity when evening came of abusing the young lady roundly. 
“It’s all your bad luck,” retorted she; “real gold would be too much for your inferior destiny.” There was an end of that; but Ma went on to say, “I always heard that fox-girls were of surpassing beauty; how is it you are not?” “Oh,” replied the young lady, “we always adapt ourselves to our company. Now you haven’t the luck of an ounce of silver to call your own; and what would you do, for instance, with a beautiful princess?
 My beauty may not be good enough for the aristocracy; but among your big-footed, burden-carrying rustics, why it may safely be called ‘surpassing.’”

A few months passed away, and then one day the young lady came and gave Ma three ounces of silver, saying, “You have often asked me for money, but in consequence of your weak luck I have always refrained from giving you any. 
Now, however, your marriage is at hand, and I here give you the cost of a wife, which you may also regard as a parting gift from me.” 
Ma replied that he wasn’t engaged, to which the young lady answered that in a few days a go-between would visit him to arrange the affair. 
“And what will she be like?” asked Ma. “Why, as your aspirations are for ‘surpassing’ beauty,” replied the young lady, “of course she will be possessed of surpassing beauty.” “I hardly expect that,” said Ma; “at any rate three ounces of silver will not be enough to get a wife.” 
“Marriages,” explained the young lady, “are made in the moon;[354] mortals have nothing to do with them.” “And why must you be going away like this?” inquired Ma. 
“Because,” answered she, “we go on shilly-shallying from day to day, and month to month, and nothing ever comes of it. I had better get you another wife and have done with you.” 
Then when morning came, she departed, giving Ma a pinch of yellow powder, saying, “In case you are ill after we are separated, this will cure you.” Next day, sure enough, a go-between did come, and Ma at once asked what the proposed bride was like; to which the former replied that she was very passable-looking. 
Four or five ounces of silver was fixed as the marriage present, Ma making no difficulty on that score, but declaring he must have a peep at the young lady.[355] The go-between said she was a respectable girl, and would never allow herself to be seen; however it was arranged that they should go to the house together, and await a good opportunity. 
So off they went, Ma remaining outside while the go-between went in, returning in a little while to tell him it was all right. “A relative of mine lives in the same court, and just now I saw the young lady sitting in the hall. We have only got to pretend we are going to see my relative, and you will be able to get a glimpse of her.” 
Ma consented, and they accordingly passed through the hall, where he saw the young lady sitting down with her head bent forward while some one was scratching her back. 
She seemed to be all that the go-between had said; but when they came to discuss the money, it appeared the young lady only wanted one or two ounces of silver, just to buy herself a few clothes, etc., at which Ma was delighted, and gave the go-between a present for her trouble, which just finished up the three ounces his fox-friend had provided. An auspicious day was chosen, and the young lady came over to his house; when lo! she was hump-backed and pigeon-breasted, with a short neck like a tortoise, and boat-shaped feet, full ten inches long. The meaning of his fox-friend’s remarks then flashed upon him.
"""


AZURE_OPENAI_ENDPOINT = "https://openai-cody.openai.azure.com/"
AZURE_OPENAI_KEY = "744f68ceda254bb7a82f4793499efedb"

class DialogueItem(BaseModel):
    text: str
    speaker: Literal["speaker-1", "speaker-2"]

class Dialogue(BaseModel):
    scratchpad: str
    dialogue: List[DialogueItem]

@retry(retry=retry_if_exception_type(AzureError))
def generate_dialogue(
    text: str = Story,
    intro_instructions: str = INSTRUCTION_TEMPLATES["podcast"]["intro"],
    text_instructions: str = INSTRUCTION_TEMPLATES["podcast"]["text_instructions"],
    scratch_pad_instructions: str = INSTRUCTION_TEMPLATES["podcast"]["scratch_pad"],
    prelude_dialog: str = INSTRUCTION_TEMPLATES["podcast"]["prelude"],
    podcast_dialog_instructions: str = INSTRUCTION_TEMPLATES["podcast"]["dialog"],
    edited_transcript: str = None,
    user_feedback: str = None,
    azure_endpoint: str = AZURE_OPENAI_ENDPOINT,
    azure_api_key: str = AZURE_OPENAI_KEY,
    azure_deployment: str = "gpt-4o"
) -> Dialogue:
    # Initialize Azure OpenAI client
    client = AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=azure_api_key,
        api_version="2024-06-01"  # Update this to the latest version as needed
    )

    prompt = f"""
    {intro_instructions}
    
    Here is the original input text:
    
    <input_text>
    {text}
    </input_text>

    {text_instructions}
    
    <scratchpad>
    {scratch_pad_instructions}
    </scratchpad>
    
    {prelude_dialog}
    
    <podcast_dialogue>
    {podcast_dialog_instructions}
    </podcast_dialogue>
    {edited_transcript or ''}
    {user_feedback or ''}

    Please generate a dialogue based on the above instructions and text. 
    The output should be in the following JSON format:
    {{
        "scratchpad": "Your thought process and notes here",
        "dialogue": [
            {{"text": "Speaker 1's line", "speaker": "speaker-1"}},
            {{"text": "Speaker 2's line", "speaker": "speaker-2"}},
            ...
        ]
    }}
    Ensure that the dialogue alternates between speaker-1 and speaker-2.
    """

    # Generate the dialogue using Azure OpenAI
    response = client.chat.completions.create(
        model=azure_deployment,  # Use the deployment name here
        messages=[
            {"role": "system", "content": "You are a helpful assistant that generates structured dialogue based on given instructions and text."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=4000,  # Adjust as needed
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None
    )

    # Extract the generated dialogue from the response
    generated_content = response.choices[0].message.content
    print(generated_content)
    try:
        # Parse the JSON content
        dialogue_dict = json.loads(generated_content)
        
        # Create and return a Dialogue object
        return Dialogue(
            scratchpad=dialogue_dict["scratchpad"],
            dialogue=[DialogueItem(**item) for item in dialogue_dict["dialogue"]]
        )
    except json.JSONDecodeError:
        raise ValueError("The generated content is not in the expected JSON format.")
    except KeyError as e:
        raise ValueError(f"The generated content is missing the required key: {e}")

# Usage example:
# dialogue = generate_dialogue(
#     text="Your input text here",
#     intro_instructions="Your intro instructions",
#     text_instructions="Your text instructions",
#     scratch_pad_instructions="Your scratchpad instructions",
#     prelude_dialog="Your prelude dialog",
#     podcast_dialog_instructions="Your podcast dialog instructions",
#     azure_endpoint="YOUR_AZURE_ENDPOINT",
#     azure_api_key="YOUR_AZURE_API_KEY",
#     azure_deployment="YOUR_AZURE_DEPLOYMENT_NAME"
# )
# 
# # Access the generated dialogue
# print(dialogue.scratchpad)
# for item in dialogue.dialogue:
#     print(f"{item.speaker}: {item.text}")

############################# Flux #############################
import requests

url = "https://api.siliconflow.cn/v1/image/generations"

payload = {
    "model": "Pro/black-forest-labs/FLUX.1-schnell",
    "prompt": "In ancient China, a masculine handsome young man wearing Hanfu driving a Tesla Model 3. High detailed, epic, photorealistic",
    "image_size": "1024x576",
}
headers = {
    "Authorization": "Bearer sk-pgftxdeonnmtkpdlprbuskmyyhnrdynwdfkcvhodkmylgzfo",
    "Content-Type": "application/json"
}

response = requests.request("POST", url, json=payload, headers=headers)

print(json.loads(response.text)["images"][0]['url'])

