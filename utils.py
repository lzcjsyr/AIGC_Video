"""
智能视频制作系统 - 工具函数模块
包含通用工具函数、错误处理和日志管理

调用关系:
- core/pipeline.py: 使用日志、异常类、JSON处理、文本清理等工具函数
- core/text.py: 使用日志、异常类、文本清理等工具函数  
- core/services.py: 使用日志、异常类、重试装饰器等工具函数
- core/media.py: 使用日志、异常类、文件操作等工具函数
- core/document_processor.py: 使用日志、目录创建、异常类等工具函数
- core/project_scanner.py: 使用日志、文件信息获取等工具函数
- web/backend/app.py: 使用日志、异常类、文件信息获取等工具函数
- cli/__main__.py: 使用日志配置和异常类
- cli/ui_helpers.py: 间接通过其他核心模块使用
"""

import os
import json
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, List

# 只定义logger对象，由具体的CLI或Web模块来配置
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
            logger.debug(f"函数 {func.__name__} 执行失败: {str(e)}")
            raise
    return wrapper

def ensure_directory_exists(directory: str) -> None:
    """确保目录存在，如不存在则创建"""
    Path(directory).mkdir(parents=True, exist_ok=True)
    logger.debug(f"确保目录存在: {directory}")

def safe_file_operation(operation: str, file_path: str, operation_func, *args, **kwargs):
    """安全的文件操作包装器，统一错误处理"""
    try:
        # 确保目录存在
        if operation in ['save', 'write', 'create']:
            ensure_directory_exists(os.path.dirname(file_path))
        
        # 执行操作
        return operation_func(*args, **kwargs)
        
    except FileNotFoundError:
        error_msg = f"文件不存在: {file_path}"
        logger.error(f"{operation}操作失败: {error_msg}")
        raise FileProcessingError(error_msg)
    except PermissionError:
        error_msg = f"文件权限不足: {file_path}"
        logger.error(f"{operation}操作失败: {error_msg}")
        raise FileProcessingError(error_msg)
    except Exception as e:
        error_msg = f"{operation}操作失败 {file_path}: {str(e)}"
        logger.error(error_msg)
        raise FileProcessingError(error_msg)


def validate_file_format(file_path: str, supported_formats: List[str]) -> bool:
    """验证文件格式"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    file_extension = Path(file_path).suffix.lower()
    if file_extension not in supported_formats:
        raise FileProcessingError(f"不支持的文件格式: {file_extension}，支持的格式: {supported_formats}")
    
    return True



def save_json_file(data: Dict[str, Any], file_path: str) -> None:
    """安全地保存JSON文件"""
    def _save():
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"JSON文件已保存: {file_path}")
    
    safe_file_operation("保存JSON", file_path, _save)

def load_json_file(file_path: str) -> Dict[str, Any]:
    """安全地加载JSON文件"""
    def _load():
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"JSON文件已加载: {file_path}")
        return data
    
    return safe_file_operation("加载JSON", file_path, _load)

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
    def _get_info():
        stat = os.stat(file_path)
        return {
            "path": file_path,
            "name": os.path.basename(file_path),
            "size": stat.st_size,
            "size_formatted": format_file_size(stat.st_size),
            "modified_time": datetime.datetime.fromtimestamp(stat.st_mtime),
            "extension": Path(file_path).suffix.lower()
        }
    
    return safe_file_operation("获取文件信息", file_path, _get_info)

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


# 导出主要函数和类
__all__ = [
    'VideoProcessingError', 'APIError', 'FileProcessingError',
    'log_function_call', 'ensure_directory_exists',
    'validate_file_format', 'save_json_file', 'load_json_file',
    'calculate_duration', 'format_file_size', 'get_file_info',
    'retry_on_failure', 'validate_required_fields', 'logger',
]

