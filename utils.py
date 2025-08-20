"""
智能视频制作系统 - 工具函数模块
包含通用工具函数、错误处理和日志管理
"""

import os
import re
import json
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('aigc_video.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('AIGC_Video')

# 降低第三方库 pdfminer 的噪声日志级别
for _name in [
    "pdfminer",
    "pdfminer.pdffont",
    "pdfminer.pdfinterp",
    "pdfminer.cmapdb",
]:
    try:
        logging.getLogger(_name).setLevel(logging.ERROR)
    except Exception:
        pass

class VideoProcessingError(Exception):
    """视频处理专用异常类"""
    pass

class APIError(Exception):
    """API调用异常类"""
    pass

class FileProcessingError(Exception):
    """文件处理异常类"""
    pass

def log_function_call(func):
    """装饰器：记录函数调用"""
    def wrapper(*args, **kwargs):
        logger.info(f"调用函数: {func.__name__}")
        try:
            result = func(*args, **kwargs)
            logger.info(f"函数 {func.__name__} 执行成功")
            return result
        except Exception as e:
            logger.error(f"函数 {func.__name__} 执行失败: {str(e)}")
            raise
    return wrapper

def ensure_directory_exists(directory: str) -> None:
    """确保目录存在，如不存在则创建"""
    Path(directory).mkdir(parents=True, exist_ok=True)
    logger.debug(f"确保目录存在: {directory}")

def clean_text(text: str) -> str:
    """清理文本内容"""
    if not text:
        return ""
    
    # 移除HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    # 标准化空白字符
    text = re.sub(r'\s+', ' ', text)
    # 移除首尾空白
    text = text.strip()
    
    return text

def validate_file_format(file_path: str, supported_formats: List[str]) -> bool:
    """验证文件格式"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    file_extension = Path(file_path).suffix.lower()
    if file_extension not in supported_formats:
        raise FileProcessingError(f"不支持的文件格式: {file_extension}，支持的格式: {supported_formats}")
    
    return True

def safe_json_loads(json_string: str) -> Dict[str, Any]:
    """安全的JSON解析"""
    try:
        # 提取JSON部分
        json_start = json_string.find('{')
        json_end = json_string.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            raise ValueError("未找到有效的JSON对象")
        
        json_content = json_string[json_start:json_end]
        return json.loads(json_content)
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {str(e)}")
        raise ValueError(f"JSON格式错误: {str(e)}")

def parse_json_robust(raw_text: str) -> Dict[str, Any]:
    """鲁棒解析：先尝试标准JSON解析，失败再用json-repair做保守修复。
    - 仅对首次'{'与末次'}'之间的子串进行修复，避免引入额外内容
    - 修复成功后再用json.loads确认为有效JSON
    """
    # 提取JSON主体
    start = raw_text.find('{')
    end = raw_text.rfind('}')
    if start == -1 or end == -1 or end < start:
        raise ValueError("未在输出中找到 JSON 对象")
    snippet = raw_text[start:end+1]
    # 1) 常规解析
    try:
        return json.loads(snippet)
    except Exception as e1:
        logger.warning(f"标准JSON解析失败，尝试修复: {e1}")
    # 2) 尝试使用 json-repair 做保守修复
    try:
        from json_repair import repair_json
    except Exception as ie:
        raise ValueError(f"JSON解析失败，且缺少json-repair依赖: {ie}")
    try:
        repaired = repair_json(snippet, ensure_ascii=False)
        return json.loads(repaired)
    except Exception as e2:
        preview = snippet[:300]
        raise ValueError(f"JSON修复解析失败: {e2}; 片段预览: {preview}")

def save_json_file(data: Dict[str, Any], file_path: str) -> None:
    """安全地保存JSON文件"""
    try:
        ensure_directory_exists(os.path.dirname(file_path))
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"JSON文件已保存: {file_path}")
    except Exception as e:
        logger.error(f"保存JSON文件失败 {file_path}: {str(e)}")
        raise FileProcessingError(f"保存文件失败: {str(e)}")

def load_json_file(file_path: str) -> Dict[str, Any]:
    """安全地加载JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"JSON文件已加载: {file_path}")
        return data
    except Exception as e:
        logger.error(f"加载JSON文件失败 {file_path}: {str(e)}")
        raise FileProcessingError(f"加载文件失败: {str(e)}")

def calculate_duration(text_length: int, speech_speed_wpm: int = 300) -> float:
    """计算文本播放时长（秒）"""
    # 中文按每分钟300字计算
    duration_seconds = (text_length / speech_speed_wpm) * 60
    return round(duration_seconds, 1)

def format_file_size(size_bytes: int) -> str:
    """格式化文件大小显示"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"

def get_file_info(file_path: str) -> Dict[str, Any]:
    """获取文件信息"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    stat = os.stat(file_path)
    
    return {
        "path": file_path,
        "name": os.path.basename(file_path),
        "size": stat.st_size,
        "size_formatted": format_file_size(stat.st_size),
        "modified_time": datetime.datetime.fromtimestamp(stat.st_mtime),
        "extension": Path(file_path).suffix.lower()
    }

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """重试装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"函数 {func.__name__} 第{attempt + 1}次尝试失败: {str(e)}，{delay}秒后重试...")
                        import time
                        time.sleep(delay)
                    else:
                        logger.error(f"函数 {func.__name__} 经过{max_retries}次尝试后仍然失败")
            
            raise last_exception
        return wrapper
    return decorator

def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> None:
    """验证必需字段"""
    missing_fields = []
    for field in required_fields:
        if field not in data or data[field] is None:
            missing_fields.append(field)
    
    if missing_fields:
        raise ValueError(f"缺少必需字段: {', '.join(missing_fields)}")

def create_processing_summary(
    input_file: str,
    original_length: int,
    target_length: int,
    actual_length: int,
    num_segments: int,
    start_time: datetime.datetime,
    end_time: datetime.datetime
) -> str:
    """创建处理摘要文本"""
    
    execution_time = (end_time - start_time).total_seconds()
    compression_ratio = (1 - actual_length / original_length) * 100 if original_length > 0 else 0
    
    summary = f"""=== 文档处理摘要 ===
处理时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}
原始文档: {os.path.basename(input_file)}
原始字数: {original_length:,}字
目标字数: {target_length}字
实际字数: {actual_length}字
压缩比例: {compression_ratio:.1f}%
分段数量: {num_segments}段
总处理时间: {execution_time:.1f}秒

=== 处理统计 ===
平均每段字数: {actual_length // num_segments}字
预估总播放时长: {calculate_duration(actual_length):.1f}秒
压缩效率: {((original_length - actual_length) / execution_time):.0f}字/秒
"""
    
    return summary

def progress_callback(current: int, total: int, operation: str = "处理"):
    """进度回调函数"""
    progress = (current / total) * 100 if total > 0 else 0
    logger.info(f"{operation}进度: {current}/{total} ({progress:.1f}%)")

def prompt_yes_no(message: str, default: bool = True) -> bool:
    """命令行确认提示，返回布尔。
    
    Args:
        message: 提示消息
        default: 默认选择（回车时采用）
    """
    try:
        suffix = "[Y/n]" if default else "[y/N]"
        while True:
            choice = input(f"\n{message} {suffix}: ").strip().lower()
            if choice == '' and default is not None:
                return default
            if choice in ['y', 'yes', '是']:
                return True
            if choice in ['n', 'no', '否']:
                return False
            print("请输入 y 或 n")
    except KeyboardInterrupt:
        print("\n操作已取消")
        return False

def prompt_choice(message: str, options: List[str], default_index: int = 0) -> str:
    """通用选项选择器，返回所选项文本。
    支持输入序号或精确匹配选项文本（不区分大小写）。
    """
    try:
        while True:
            print(f"\n{message}")
            for i, opt in enumerate(options, 1):
                prefix = "*" if (i - 1) == default_index else " "
                print(f" {prefix} {i}. {opt}")
            raw = input(f"请输入序号 (默认 {default_index+1}): ").strip()
            if raw == "":
                return options[default_index]
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            # 文本匹配
            for opt in options:
                if raw.lower() == opt.lower():
                    return opt
            print("无效输入，请重试。")
    except KeyboardInterrupt:
        print("\n操作已取消")
        return options[default_index]

def make_safe_title(title: str) -> str:
    """根据合成命名规则，生成安全的标题前缀。"""
    safe_title = (
        title.replace(' ', '_')
             .replace('/', '_')
             .replace('\\', '_')
             .replace(':', '_')
             .replace('?', '_')
             .replace('*', '_')
             .replace('"', '_')
             .replace('<', '_')
             .replace('>', '_')
             .replace('|', '_')
    )
    return safe_title

def validate_media_assets(script_data: Dict[str, Any], images_dir: str, voice_dir: str) -> Dict[str, Any]:
    """校验图片、音频与脚本段落是否匹配，及命名规范。
    
    要求：
    - 图片: segment_1.png...segment_N.png 连续且齐全
    - 音频: {safe_title}_1.wav...{safe_title}_N.wav 或 mp3，连续且齐全
    - 数量与 script_data['segments'] 一致
    """
    issues: List[str] = []
    segments = script_data.get('segments', [])
    num_segments = len(segments)
    title = script_data.get('title', 'untitled')
    safe_title = make_safe_title(title)

    # 收集实际文件
    try:
        image_files = [f for f in os.listdir(images_dir) if os.path.isfile(os.path.join(images_dir, f))]
    except Exception:
        image_files = []
    try:
        audio_files = [f for f in os.listdir(voice_dir) if os.path.isfile(os.path.join(voice_dir, f))]
    except Exception:
        audio_files = []

    # 解析编号
    image_indices: List[int] = []
    for f in image_files:
        m = re.match(r'^segment_(\d+)\.png$', f)
        if m:
            image_indices.append(int(m.group(1)))
    audio_indices: List[int] = []
    for f in audio_files:
        m = re.match(rf'^{re.escape(safe_title)}_(\d+)\.(wav|mp3)$', f)
        if m:
            audio_indices.append(int(m.group(1)))

    # 基础数量检查
    if len(image_indices) != num_segments:
        issues.append(f"图片数量不匹配：期望{num_segments}张，实际{len(image_indices)}张")
    if len(audio_indices) != num_segments:
        issues.append(f"音频数量不匹配：期望{num_segments}段，实际{len(audio_indices)}段")

    # 连续性检查（1..N）
    expected_set = set(range(1, num_segments + 1))
    missing_images = sorted(list(expected_set - set(image_indices)))
    extra_images = sorted(list(set(image_indices) - expected_set))
    if missing_images:
        issues.append(f"缺少图片: segment_{missing_images[0]}...（共{len(missing_images)}个缺口）")
    if extra_images:
        issues.append(f"存在多余图片编号: {extra_images}")

    missing_audio = sorted(list(expected_set - set(audio_indices)))
    extra_audio = sorted(list(set(audio_indices) - expected_set))
    if missing_audio:
        issues.append(f"缺少音频: {safe_title}_{missing_audio[0]}.*（共{len(missing_audio)}个缺口）")
    if extra_audio:
        issues.append(f"存在多余音频编号: {extra_audio}")

    ok = len(issues) == 0
    return {
        'ok': ok,
        'issues': issues,
        'safe_title': safe_title,
        'images_dir': images_dir,
        'voice_dir': voice_dir,
        'num_segments': num_segments
    }

class ProgressTracker:
    """进度跟踪器"""
    
    def __init__(self, total_steps: int, operation_name: str = "处理"):
        self.total_steps = total_steps
        self.current_step = 0
        self.operation_name = operation_name
        self.start_time = datetime.datetime.now()
    
    def step(self, message: str = ""):
        """前进一步"""
        self.current_step += 1
        progress = (self.current_step / self.total_steps) * 100
        
        elapsed = (datetime.datetime.now() - self.start_time).total_seconds()
        if self.current_step > 0 and elapsed > 0:
            eta = elapsed * (self.total_steps - self.current_step) / self.current_step
            eta_str = f"预计剩余: {eta:.0f}秒"
        else:
            eta_str = ""
        
        log_msg = f"{self.operation_name}进度: {self.current_step}/{self.total_steps} ({progress:.1f}%)"
        if message:
            log_msg += f" - {message}"
        if eta_str:
            log_msg += f" - {eta_str}"
        
        logger.info(log_msg)
    
    def complete(self):
        """标记完成"""
        total_time = (datetime.datetime.now() - self.start_time).total_seconds()
        logger.info(f"{self.operation_name}完成！总耗时: {total_time:.1f}秒")

def scan_input_files(input_dir: str = "input") -> List[Dict[str, Any]]:
    """
    扫描input文件夹中的PDF和EPUB文件
    
    Args:
        input_dir: 输入文件夹路径
    
    Returns:
        List[Dict[str, Any]]: 文件信息列表，包含路径、名称、大小等信息
    """
    # 将相对路径锚定到项目目录（本文件所在目录）
    if not os.path.isabs(input_dir):
        input_dir = os.path.join(os.path.dirname(__file__), input_dir)
    
    if not os.path.exists(input_dir):
        logger.warning(f"输入目录不存在: {input_dir}")
        return []
    
    supported_extensions = ['.pdf', '.epub']
    files = []
    
    logger.info(f"正在扫描 {input_dir} 文件夹...")
    
    try:
        for file_name in os.listdir(input_dir):
            file_path = os.path.join(input_dir, file_name)
            
            # 跳过目录
            if os.path.isdir(file_path):
                continue
            
            # 检查文件扩展名
            file_extension = Path(file_path).suffix.lower()
            if file_extension in supported_extensions:
                file_info = get_file_info(file_path)
                files.append(file_info)
                logger.debug(f"找到文件: {file_name} ({file_info['size_formatted']})")
    
    except Exception as e:
        logger.error(f"扫描文件夹失败: {str(e)}")
        raise FileProcessingError(f"扫描文件夹失败: {str(e)}")
    
    # 按修改时间排序，最新的在前
    files.sort(key=lambda x: x['modified_time'], reverse=True)
    
    logger.info(f"共找到 {len(files)} 个文件 (PDF: {sum(1 for f in files if f['extension'] == '.pdf')}, EPUB: {sum(1 for f in files if f['extension'] == '.epub')})")
    
    return files

def display_file_menu(files: List[Dict[str, Any]]) -> None:
    """
    显示文件选择菜单
    
    Args:
        files: 文件信息列表
    """
    print("\n" + "="*60)
    print("📚 发现以下可处理的文件:")
    print("="*60)
    
    if not files:
        print("❌ 在input文件夹中未找到PDF或EPUB文件")
        print("请将要处理的PDF或EPUB文件放入input文件夹中")
        return
    
    for i, file_info in enumerate(files, 1):
        file_type = "📖 EPUB" if file_info['extension'] == '.epub' else "📄 PDF"
        modified_date = file_info['modified_time'].strftime('%Y-%m-%d %H:%M')
        
        print(f"{i:2}. {file_type} {file_info['name']}")
        print(f"     大小: {file_info['size_formatted']} | 修改时间: {modified_date}")
        print()

def get_user_file_selection(files: List[Dict[str, Any]]) -> Optional[str]:
    """
    获取用户的文件选择
    
    Args:
        files: 文件信息列表
    
    Returns:
        Optional[str]: 选择的文件路径，如果用户取消则返回None
    """
    if not files:
        return None
    
    while True:
        try:
            print("="*60)
            choice = input(f"请选择要处理的文件 (1-{len(files)}) 或输入 'q' 退出: ").strip()
            
            if choice.lower() == 'q':
                print("👋 程序已取消")
                return None
            
            file_index = int(choice) - 1
            
            if 0 <= file_index < len(files):
                selected_file = files[file_index]
                print(f"\n✅ 您选择了: {selected_file['name']}")
                print(f"   文件大小: {selected_file['size_formatted']}")
                print(f"   文件类型: {selected_file['extension'].upper()}")
                # 直接返回所选文件路径，无需再次确认
                return selected_file['path']
            else:
                print(f"❌ 无效选择，请输入 1-{len(files)} 之间的数字")
                
        except ValueError:
            print("❌ 请输入有效的数字")
        except KeyboardInterrupt:
            print("\n\n👋 程序已取消")
            return None

def interactive_file_selector(input_dir: str = "input") -> Optional[str]:
    """
    交互式文件选择器
    
    Args:
        input_dir: 输入文件夹路径
    
    Returns:
        Optional[str]: 选择的文件路径，如果用户取消则返回None
    """
    print("\n🚀 智能视频制作系统")
    print("正在扫描可处理的文件...")
    
    # 扫描文件
    files = scan_input_files(input_dir)
    
    # 显示菜单
    display_file_menu(files)
    
    # 获取用户选择
    return get_user_file_selection(files)

# 导出主要函数和类
__all__ = [
    'VideoProcessingError', 'APIError', 'FileProcessingError',
    'log_function_call', 'ensure_directory_exists', 'clean_text',
    'validate_file_format', 'safe_json_loads', 'save_json_file', 'load_json_file',
    'calculate_duration', 'format_file_size', 'get_file_info',
    'retry_on_failure', 'validate_required_fields', 'create_processing_summary',
    'progress_callback', 'ProgressTracker', 'logger',
    'scan_input_files', 'display_file_menu', 'get_user_file_selection', 'interactive_file_selector'
]