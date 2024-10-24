from genai_api import text_to_image
from datetime import datetime
from pathlib import Path
import os, requests

def generate_and_save_images(prompt, num_images=1, size="1024x1024", server="siliconflow", model="black-forest-labs/FLUX.1-schnell"):
    """
    生成多张AI图片并保存到桌面的'AI Image'文件夹
    参数:
        prompt: 图片生成提示词
        num_images: 需要生成的图片数量 (最大20张)
        size: 图片尺寸
        server: 服务器选择 ('siliconflow' 或 'openai')
        model: 模型选择
    返回:
        生成的所有图片路径列表
    """
    # 验证图片数量限制
    if not isinstance(num_images, int) or num_images < 1:
        raise ValueError("图片数量必须是正整数")
    if num_images > 20:
        raise ValueError("单次最多只能生成20张图片")
    
    # 创建保存路径
    save_dir = Path.home() / "Desktop" / "AI Image"
    save_dir.mkdir(exist_ok=True)
    
    # 生成时间戳和模型信息用于文件名
    timestamp = datetime.now().strftime("%m%d_%H%M")
    model_name = model.split('/')[-1]  # 提取模型名称的最后一部分
    
    saved_paths = []
    
    for i in range(num_images):
        try:
            # 生成图片
            image_url = text_to_image(prompt, size, server, model)
            if not image_url:
                raise Exception(f"第{i+1}张图片生成失败")
            
            # 下载图片
            response = requests.get(image_url)
            if response.status_code != 200:
                raise Exception(f"第{i+1}张图片下载失败")
            
            # 生成文件名，添加序号
            filename = f"{timestamp}_{server}_{model_name}_{i+1}.png"
            save_path = save_dir / filename
            
            # 保存图片
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            saved_paths.append(str(save_path))
            print(f"成功生成第 {i+1}/{num_images} 张图片")
            
        except Exception as e:
            print(f"生成第 {i+1} 张图片时出错: {str(e)}")
            continue
    
    return saved_paths

# 使用示例
if __name__ == "__main__":
    
    # 提示词
    prompt = """
    a beautiful sunset over mountains with a lake in the background 
    and a topless young women sitting (front view) on a bench in the foreground
    """
    
    try:
        saved_paths = generate_and_save_images(
            prompt=prompt,
            num_images=3,
            size="1024x1024",
            server="siliconflow",
            model="stabilityai/stable-diffusion-3-5-large"
        )
        print("\n所有图片已保存至:")
        for path in saved_paths:
            print(path)
            
    except Exception as e:
        print(f"错误: {str(e)}")