from langchain.llms import AzureOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List
import os
from dotenv import load_dotenv

from functions import (
    generate_and_save_images, text_to_speech, write_summary_and_plots
)

# Load environment variables
load_dotenv()
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_KEY = os.getenv('AZURE_OPENAI_KEY')

class Summary(BaseModel):
    title: str = Field(description="The title of the story")
    summary: str = Field(description="A summary of the story, 2000-3000 words")
    word_count: int = Field(description="The word count of the summary")
    main_themes: List[str] = Field(description="A list of main themes in the story")
    key_characters: List[dict] = Field(description="A list of key characters with their descriptions")

class Plot(BaseModel):
    num_plot: str = Field(description="Number of the plot")
    plot_title: str = Field(description="Title of the plot")
    plot_description: str = Field(description="Description of the plot")
    image_info: dict = Field(description="Information for image generation")

class Plots(BaseModel):
    characters: List[dict] = Field(description="List of main characters")
    plots: List[Plot] = Field(description="List of plot points")

def setup_llm():
    return AzureOpenAI(
        deployment_name="gpt-4o",
        model_name="gpt-4o",
        temperature=0.1,
        max_tokens=4000
    )

def summarize_story(llm, story):
    summary_parser = PydanticOutputParser(pydantic_object=Summary)
    summary_prompt = PromptTemplate(
        template="Summarize the following story:\n\n{story}\n\n{format_instructions}",
        input_variables=["story"],
        partial_variables={"format_instructions": summary_parser.get_format_instructions()}
    )
    summary_chain = LLMChain(llm=llm, prompt=summary_prompt)
    summary_output = summary_chain.run(story=story)
    return summary_parser.parse(summary_output)

def split_plots(llm, story, num_plots):
    plots_parser = PydanticOutputParser(pydantic_object=Plots)
    plots_prompt = PromptTemplate(
        template="Split the following story into {num_plots} distinct plot points:\n\n{story}\n\n{format_instructions}",
        input_variables=["story", "num_plots"],
        partial_variables={"format_instructions": plots_parser.get_format_instructions()}
    )
    plots_chain = LLMChain(llm=llm, prompt=plots_prompt)
    plots_output = plots_chain.run(story=story, num_plots=num_plots)
    return plots_parser.parse(plots_output)

def main(story, model_type="FLUX", num_plots=5, num_images=1, output_dir=None, voice_name="en-US-JennyNeural"):
    try:
        # Input validation
        if not isinstance(story, str) or len(story) < 1000:
            raise ValueError("Story must be a string with at least 1000 characters")
        if not 1 < num_plots <= 20:
            raise ValueError("num_plots must be between 2 and 20")
        if not 0 <= num_images <= 5:
            raise ValueError("num_images must be between 1 and 5")
        if model_type not in ["FLUX", "OpenAI"]:
            raise ValueError("model_type must be either 'FLUX' or 'OpenAI'")

        llm = setup_llm()
        
        # Create folders
        base_dir = output_dir or os.path.expanduser("~/Desktop")
        visualization_folder = os.path.join(base_dir, "Story Visualization")
        images_folder = os.path.join(visualization_folder, "Images")
        os.makedirs(images_folder, exist_ok=True)
        
        # Process story
        summary = summarize_story(llm, story)
        plots = split_plots(llm, story, num_plots)
        write_summary_and_plots(visualization_folder, summary, plots)
        
        # Generate images and prompts
        if num_images == 0:
             print("Skip images generation.")
        else: 
            results = [generate_and_save_images(llm, plots_json=plots.dict(), plot_index=i+1, 
                                                num_images=num_images, images_folder=images_folder, 
                                                model_type=model_type) for i in range(len(plots.plots))]
        
        # Generate audio
        if voice_name is None:
            print("Skip audio generation.")
            audio_path = None
        else:
            audio_path = text_to_speech(summary.summary, os.path.join(visualization_folder, "story_summary.wav"), voice_name)

        return {"summary": summary.dict(), 
                "images": [path for result in results for path in result[0]] if num_images > 0 else [], 
                "audio": audio_path}
    
    except ValueError as ve:
        print(f"Input error: {str(ve)}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    return None

if __name__ == "__main__":
    with open('story.txt', 'r') as file:
        story = file.read()
    result = main(story, model_type="FLUX", num_plots=5, num_images=0, output_dir=None, voice_name="en-US-AvaMultilingualNeural")
    if result and result["audio"]:
        print("Hooray! The AIGC task was completed successfully!")
    elif result:
        print("The AIGC task was completed, but audio generation failed.")
    else:
        print("The task could not be completed due to an error.")