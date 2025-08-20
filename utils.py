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

# 导出主要函数和类
__all__ = [
    'VideoProcessingError', 'APIError', 'FileProcessingError',
    'log_function_call', 'ensure_directory_exists', 'clean_text',
    'validate_file_format', 'safe_json_loads', 'save_json_file', 'load_json_file',
    'calculate_duration', 'format_file_size', 'get_file_info',
    'retry_on_failure', 'validate_required_fields', 'create_processing_summary',
    'progress_callback', 'ProgressTracker', 'logger'
]