import os
import sys
import datetime
import requests
from urllib.parse import urlparse
from io import BytesIO
from PIL import Image, UnidentifiedImageError

# Ensure project root is on sys.path when running from tools/
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.services import text_to_image_doubao, text_to_audio_bytedance


def ensure_temp_dir(project_root: str) -> str:
    temp_dir = os.path.join(project_root, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def sanitize_filename(name: str) -> str:
    # 保留常见安全字符；其余替换为下划线
    safe_chars = "-_().（）[]【】{}，。、“”‘’ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(ch if (ch.isalnum() or ch in safe_chars) else "_" for ch in name)


def is_valid_http_url(url: str) -> bool:
    """Basic validation to ensure we got a usable http(s) URL."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def first_n_chars(text: str, n: int) -> str:
    text = text.strip()
    return text[:n] if len(text) > n else text


def build_filename(prompt: str, ext: str) -> str:
    prefix_raw = first_n_chars(prompt, 6)
    prefix = sanitize_filename(prefix_raw).strip(" _") or "untitled"
    # 使用 月日_时分，与现有项目时间后缀风格保持一致
    # 扩展到包含秒，降低同一分钟内的重名概率
    time_suffix = datetime.datetime.now().strftime("%m%d_%H%M%S")
    return f"{prefix}_{time_suffix}{ext}"


def read_document(file_path: str) -> str:
    """
    读取文档内容，使用统一的DocumentReader
    """
    from core.document_reader import DocumentReader
    reader = DocumentReader()
    content, _ = reader.read(file_path)
    return content


def get_text_input() -> str:
    print("\n请选择文字输入方式：")
    print("  1) 直接输入")
    print("  2) 从文档读取")
    
    while True:
        choice = input("请输入选项 (1/2): ").strip()
        if choice in ("1", "2"):
            break
        print("无效输入，请输入 1 或 2。")
    
    if choice == "1":
        text = input("\n请输入文字内容：").strip()
        if not text:
            raise ValueError("文字内容不能为空")
        return text
    else:
        while True:
            file_path = input("\n请输入文档路径：").strip()
            
            # 处理空路径或引号包围的路径
            if not file_path:
                print("❌ 文档路径不能为空。")
                continue
                
            # 移除可能的引号
            if (file_path.startswith('"') and file_path.endswith('"')) or \
               (file_path.startswith("'") and file_path.endswith("'")):
                file_path = file_path[1:-1].strip()
                
            # 再次检查去除引号后是否为空
            if not file_path:
                print("❌ 文档路径不能为空。")
                continue
            
            try:
                text = read_document(file_path)  # 使用本地定义的函数
                print(f"✅ 成功读取文档，文字长度：{len(text)} 字符")
                preview = first_n_chars(text, 100)
                print(f"内容预览：{preview}{'...' if len(text) > 100 else ''}")
                return text
            except (ValueError, FileNotFoundError) as e:
                print(f"❌ 文件路径问题：{e}")
                retry = input("是否重新输入文档路径？(y/n): ").strip().lower()
                if retry != 'y':
                    raise RuntimeError("用户取消文档读取")
            except Exception as e:
                print(f"❌ 读取文档失败：{e}")
                retry = input("是否重新输入文档路径？(y/n): ").strip().lower()
                if retry != 'y':
                    raise RuntimeError("用户取消文档读取")


def generate_image(prompt: str, save_dir: str, size: str = "1024x1024", model: str = "doubao-seedream-3-0-t2i-250415") -> str:
    os.makedirs(save_dir, exist_ok=True)

    image_url = text_to_image_doubao(prompt=prompt, size=size, model=model)
    if not image_url or not isinstance(image_url, str):
        raise RuntimeError("图像生成失败：未返回URL")
    if not is_valid_http_url(image_url):
        raise RuntimeError(f"图像生成失败：URL无效或不受支持 -> {image_url}")

    # 强制保存为 PNG（无论返回URL的原始扩展名）
    filename = build_filename(prompt, ".png")
    output_path = os.path.join(save_dir, filename)

    resp = requests.get(image_url, timeout=60)
    resp.raise_for_status()

    try:
        with Image.open(BytesIO(resp.content)) as img_loaded:
            # 强制解码，尽早暴露错误
            img_loaded.load()
            # 统一转换到适合PNG的模式（保持透明度）
            if img_loaded.mode in ("RGBA", "LA") or (img_loaded.mode == "P" and "transparency" in img_loaded.info):
                img_converted = img_loaded.convert("RGBA")
            else:
                img_converted = img_loaded.convert("RGB")

        temp_path = f"{output_path}.part"
        img_converted.save(temp_path, format="PNG")
        os.replace(temp_path, output_path)
    except UnidentifiedImageError as e:
        raise RuntimeError(f"下载的内容不是有效图片：{e}")
    except Exception as e:
        raise RuntimeError(f"下载或转换PNG失败：{e}")

    return output_path


def generate_audio(prompt: str, save_dir: str, voice: str = "zh_male_yuanboxiaoshu_moon_bigtts", encoding: str = "wav") -> str:
    os.makedirs(save_dir, exist_ok=True)

    enc_norm = encoding.lower().lstrip(".")
    allowed = {"wav", "mp3"}
    if enc_norm not in allowed:
        raise ValueError(f"不支持的音频编码：{encoding}，仅支持：{', '.join(sorted(allowed))}")

    ext = f".{enc_norm}"
    filename = build_filename(prompt, ext)
    output_path = os.path.join(save_dir, filename)
    ok = text_to_audio_bytedance(text=prompt, output_filename=output_path, voice=voice, encoding=enc_norm)
    if not ok or not os.path.exists(output_path):
        raise RuntimeError("语音合成失败")
    return output_path


def main(
    image_size: str = "1024x1024",
    image_model: str = "doubao-seedream-3-0-t2i-250415",
    tts_voice: str = "zh_male_yuanboxiaoshu_moon_bigtts",
    audio_encoding: str = "wav",
) -> int:
    project_root = os.path.dirname(__file__)
    temp_dir = ensure_temp_dir(project_root)

    print("\n======================")
    print("独立生成：图片 或 音频")
    print("======================\n")
    print(f"当前参数：图片尺寸={image_size} | 图片模型={image_model}")
    print(f"当前参数：语音音色={tts_voice} | 音频编码={audio_encoding}")
    print("请选择要生成的类型：")
    print("  1) 图片")
    print("  2) 音频")
    print("  q) 退出")

    while True:
        choice = input("请输入选项 (1/2/q): ").strip().lower()
        if choice in ("1", "2", "q"):
            break
        print("无效输入，请输入 1、2 或 q。")

    if choice == "q":
        print("已退出。")
        return 0

    try:
        if choice == "1":
            # 生成图片
            prompt = input("\n请输入提示词：").strip()
            if not prompt:
                print("提示词不能为空。")
                return 1
            print("\n正在生成图片…")
            out_path = generate_image(prompt, temp_dir, size=image_size, model=image_model)
            print(f"完成！图片已保存：{out_path}")
        else:
            # 生成音频
            text_content = get_text_input()
            print("\n正在合成音频…")
            out_path = generate_audio(text_content, temp_dir, voice=tts_voice, encoding=audio_encoding)
            print(f"完成！音频已保存：{out_path}")
        return 0
    except KeyboardInterrupt:
        print("\n已取消。")
        return 1
    except Exception as e:
        print(f"\n❌ 失败：{e}")
        return 1


if __name__ == "__main__":
    # ================= 可在下方调整主要参数（便于修改） =================
    # 可选尺寸：1024x1024 | 864x1152 | 1152x864 | 1280x720 | 720x1280 | 832x1248 | 1248x832 | 1512x648
    IMAGE_SIZE = "1280x720" 
    IMAGE_MODEL = "doubao-seedream-3-0-t2i-250415"
    TTS_VOICE = "zh_male_yuanboxiaoshu_moon_bigtts"  # 可在豆包/字节控制台选择其他音色
    AUDIO_ENCODING = "wav"  # 可选：wav | mp3

    sys.exit(main(
        image_size=IMAGE_SIZE,
        image_model=IMAGE_MODEL,
        tts_voice=TTS_VOICE,
        audio_encoding=AUDIO_ENCODING,
    ))


