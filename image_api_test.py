from genai_api import text_to_image
import os
from datetime import datetime
import requests
from pathlib import Path

def generate_and_save_image(prompt, size="1024x1024", server="siliconflow", model="black-forest-labs/FLUX.1-schnell"):
    """
    生成AI图片并保存到桌面的'AI Image'文件夹
    参数:
        prompt: 图片生成提示词
        size: 图片尺寸
        server: 服务器选择 ('siliconflow' 或 'openai')
        model: 模型选择
    """
    # 创建保存路径
    save_dir = Path.home() / "Desktop" / "AI Image"
    save_dir.mkdir(exist_ok=True)
    
    # 生成图片
    image_url = text_to_image(prompt, size, server, model)
    if not image_url:
        raise Exception("图片生成失败")
    
    # 下载图片
    response = requests.get(image_url)
    if response.status_code != 200:
        raise Exception("图片下载失败")
    
    # 生成包含时间戳和模型信息的文件名
    timestamp = datetime.now().strftime("%m%d_%H%M")
    model_name = model.split('/')[-1]  # 提取模型名称的最后一部分
    filename = f"{timestamp}_{server}_{model_name}.png"
    
    # 保存图片
    with open(save_dir / filename, 'wb') as f:
        f.write(response.content)
    
    return str(save_dir / filename)

# 使用示例
if __name__ == "__main__":
    
    # 提示词
    prompt = """
    a beautiful sunset over mountains with a lake in the background
    """
    
    try:
        saved_path = generate_and_save_image(
            prompt=prompt,
            size="1024x1024",
            server="siliconflow",
            model="black-forest-labs/FLUX.1-schnell"
        )
        print(f"图片已保存至: {saved_path}")
    except Exception as e:
        print(f"错误: {str(e)}")