from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips, VideoFileClip
from typing import Optional, Dict, Any
from docx.oxml.ns import qn
from docx.shared import Pt
from docx import Document
from io import BytesIO
from PIL import Image

import requests, json, os, re
from knowledge_prompt_cn import parser_system_prompt, generate_image_system_prompt, content
from genai_api import text_to_text, text_to_image, text_to_audio

################ Content Parser ################
def content_parser(server: str, model: str, content: str, num_plots: int) -> Optional[Dict[str, Any]]:
    try:
        user_message = f"Parse this content into {num_plots} plots. The content is as following:\n\n{content}"
        output = text_to_text(server=server, model=model, prompt=user_message, system_message=parser_system_prompt, max_tokens=4096, temperature=0.7)
        if output is None:
            raise ValueError("未能从 API 获取响应。")
        
        json_start = output.find('{')
        json_end = output.rfind('}') + 1
        if json_start == -1 or json_end == 0:
            raise ValueError("未在'output'中找到 JSON 对象。")
        
        parsed_content = json.loads(output[json_start:json_end])
        
        required_keys = ["title", "themes", "segmentations"]
        if not all(key in parsed_content for key in required_keys):
            missing_keys = [key for key in required_keys if key not in parsed_content]
            raise ValueError(f"生成的 JSON 缺少必需的 Key: {', '.join(missing_keys)}")
        
        return parsed_content
    
    except json.JSONDecodeError:
        # Avoid printing 'output' as it may not be defined correctly.
        print("错误：解析 JSON 输出失败。")
        return None
    except Exception as e:
        print(f"内容处理错误: {e}")
        return None

def parsed_saver(parsed_json: Dict[str, Any], saving_path: str = None) -> None:

    doc = Document()
    
    # 设置默认字体为宋体
    style = doc.styles['Normal']
    style.font.name = '宋体'
    style._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    
    # 设置1.5倍行距
    style.paragraph_format.line_spacing = 1.5
    
    # Set default path to desktop if no path is provided
    if saving_path is None:
        saving_path = os.path.join(os.path.expanduser("~"), "Desktop")
    
    def process_value(value: Any, level: int = 1) -> None:
        """
        Recursively process JSON values with highlighted keys and sized text.
        
        Args:
            value: JSON value (dict, list, or primitive)
            level: Nesting level for sizing (outer = larger)
        """
        if isinstance(value, dict):
            for key, val in value.items():
                if isinstance(val, (dict, list)):
                    # Add heading with bold text
                    heading = doc.add_heading('', level=min(level, 9))
                    run = heading.add_run(str(key).capitalize())
                    font = run.font
                    font.name = '宋体'
                    run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
                    
                    # 只有一级标题保持大字体，其他标题只需要加粗
                    if level == 1:
                        font.size = Pt(20)
                    run.bold = True
                    
                    process_value(val, level + 1)
                else:
                    # Add key-value pair with bold key
                    para = doc.add_paragraph('')
                    key_run = para.add_run(f"{str(key).capitalize()}: ")
                    key_run.font.name = '宋体'
                    key_run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
                    key_run.bold = True  # 加粗而不改变字体大小
                    
                    value_run = para.add_run(str(val))
                    value_run.font.name = '宋体'
                    value_run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, (dict, list)):
                    process_value(item, level + 1)
                else:
                    para = doc.add_paragraph('')
                    run = para.add_run(str(item))
                    run.font.name = '宋体'
                    run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        
        else:
            para = doc.add_paragraph('')
            run = para.add_run(str(value))
            run.font.name = '宋体'
            run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')

    # Get and add title
    title = parsed_json.get('title', 'Untitled Document')
    title_heading = doc.add_heading(title, 0)
    for run in title_heading.runs:
        run.font.name = '宋体'
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    
    # Process all top-level keys except title
    for key, value in parsed_json.items():
        if key != 'title':
            heading = doc.add_heading('', level=1)
            run = heading.add_run(str(key).capitalize())
            run.font.name = '宋体'
            run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
            run.font.size = Pt(20)  # 保持一级标题的大字体
            run.bold = True
            process_value(value)
    
    # Save the document
    doc_path = os.path.join(saving_path, f"{title}.docx")
    doc.save(doc_path)
    print(f"文件保存到：{doc_path}")

################ Image Generation ################
def generate_image_prompt(server, model, prompt, regenerate=False):
    
    # Define system message for image prompt generation
    system_message = generate_image_system_prompt
    if regenerate:
        system_message += "\n\nCreate a safe, non-controversial prompt that captures the essence of the scene."
    
    response = text_to_text(server = server, model = model, prompt = prompt, system_message = system_message, max_tokens=4096, temperature=0.7)
    return response

def generate_images(image_server, image_model, llm_server, llm_model, parsed_content, plot_index, size, num_images=1, saving_path=None):
    
    if saving_path is None:
        saving_path = os.path.join(os.path.expanduser('~'), 'Desktop')
    if num_images < 1:
        raise ValueError("'num_images' 必须大于等于 1.")
    
    # Extract input for image prompt from story content
    if "key_characters" in parsed_content:
        plot = parsed_content["segmentations"][plot_index - 1]
        characters = [char for char in parsed_content["key_characters"] if char["name"] in plot["characters_name"]]
        input_for_prompt = f"Plot: {plot['plot']}\nCharacters: {characters}"
    else:
        plot = parsed_content["segmentations"][plot_index - 1]
        input_for_prompt = f"Generate images according to the following information: \n{plot}"

    image_prompt = generate_image_prompt(server=llm_server, model=llm_model, prompt=input_for_prompt, regenerate=False)

    images = []
    # Generate images
    for i in range(num_images):
        for attempt in range(5):
            try:
                image_url = text_to_image(server=image_server, model=image_model, prompt=image_prompt, size=size)
                image = Image.open(BytesIO(requests.get(image_url).content))
                images.append(image)
                print(f"用模型 {image_model} 为第 {plot_index} 幕生成第 {i+1} 张图片 .")
                break
            except Exception as e:
                if 'content_policy_violation' in str(e) and attempt < 4:
                    print(f"违反监管政策。 重新生成提示词 (Attempt {attempt+1})")
                    image_prompt = generate_image_prompt(server=llm_server, model=llm_model, prompt=input_for_prompt, regenerate=True)
                else:
                    print(f"生成图片失败: {e}")
                    break

    # Save generated images
    image_paths = []
    for j, image in enumerate(images, 1):
        safe_model_name = image_model.replace('/', '_')
        image_path = os.path.join(saving_path, f"plot_{plot_index}_image_{j}_{safe_model_name}.png")
        image.save(image_path)
        image_paths.append(image_path)
    
    print(f"为第 {plot_index} 幕保存第 {len(image_paths)} 张图片.")
    return image_paths, image_prompt

def generate_and_save_images(image_server, image_model, llm_server, llm_model, parsed_content, num_plots, num_images, size, saving_path):
    image_paths = []
    image_prompts = []
    
    if num_images > 0:
        for i in range(num_plots):
            plot_images, prompt = generate_images(image_server, image_model, llm_server, llm_model, 
                                                  parsed_content, plot_index=i+1, size=size, num_images=num_images, saving_path=saving_path)
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
        print(f"把提示词保存到: {prompt_file}")
    else:
        print("跳过图片生成环节。")
        prompt_file = None
    
    return image_paths, prompt_file

################ Audio and Video ################
def prepare_images_for_video(images_folder, num_plots, num_images):
    
    # Check input
    if not os.path.exists(images_folder):
        raise FileNotFoundError(f"Image folder does not exist: {images_folder}")
    if num_plots <= 0 or num_images <= 0:
        raise ValueError("num_plots 和 num_images 必须大于 0。")

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
                print(f"错误: 第 {plot} 幕没有对应的图片。")
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
                        print("选择无效，请重新输入。")
                except ValueError:
                    print("选择无效，请重新输入。")
    
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
        print(f"生成视频错误: {str(e)}")
        return None
    
def create_media(parsed_content, audio_paths, image_paths, video_paths, generate_video=False, server="openai", voice="alloy"):

    audio_files = []
    plot_videos = []
    
    # Process each plot segment
    for i, plot in enumerate(parsed_content['segmentations']):
        # Generate audio for current plot
        audio_file = text_to_audio(
            server=server,
            text=plot['plot'],
            output_filename=os.path.join(audio_paths, f"plot_{i+1}.wav"),
            voice=voice
        )
        print(f"已生成第 {i+1} 幕的音频。")
        
        if not audio_file:
            print(f"第 {i+1} 幕的音频生成错误。")
            continue
            
        audio_files.append(audio_file)
        
        # If video generation is requested, create video for current plot segment
        if generate_video:
            plot_image_paths = image_paths[i:i+1]  # One image per plot
            plot_video_path = os.path.join(video_paths, f"plot_{i+1}.mp4")
            plot_video_path = create_video(audio_file, plot_image_paths[0], plot_video_path)
            
            if plot_video_path:
                plot_videos.append(plot_video_path)
                print(f"第 {i+1} 幕的视频已生成: {plot_video_path}")
            else:
                print(f"第 {i+1} 幕的视频生成错误。")
    
    # If no audio files were generated, return None
    if not audio_files:
        print("无法生成音频文件，无法继续。")
        return None
        
    # If video generation was not requested, return the list of audio files
    if not generate_video:
        print(f"生成 {len(audio_files)} 个音频文件。")
        return audio_files
    
    # If video generation was requested but no videos were created, return None
    if not plot_videos:
        print("由于某些原因，无法生成视频，无法继续。")
        return None
        
    # Concatenate all plot videos into final video
    final_video_path = os.path.join(video_paths, "full_video.mp4")
    clips = [VideoFileClip(video) for video in plot_videos]
    final_video = concatenate_videoclips(clips)
    final_video.write_videofile(final_video_path)
    print(f"完成的视频已生成: {final_video_path}")
    
    return final_video_path