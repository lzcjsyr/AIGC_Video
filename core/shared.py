"""
智能视频制作系统 - 工具函数模块
提供通用工具函数、错误处理和日志管理

主要功能:
- 日志配置和管理
- 自定义异常类（APIError, VideoProcessingError）
- JSON 文件处理（加载、保存、修复）
- 文件信息获取和操作
- 重试装饰器和错误处理
- 文本清理和规范化

被以下模块调用:
- core/pipeline.py: 兼容入口
- core/domain/*: 业务层能力复用
- core/pipeline/*: 编排与流程管理
- cli/__main__.py: 日志配置和异常类
- cli/ui_helpers.py: 间接通过核心模块使用
"""

import os
import json
import logging
import datetime
import functools
import random
import re
import time
from pathlib import Path
from typing import Dict, Any

# 只定义logger对象，由具体的CLI或Web模块来配置
logger = logging.getLogger('AIGC_Video')

SUPPORTED_INPUT_EXTENSIONS = (
    ".pdf",
    ".epub",
    ".mobi",
    ".azw3",
    ".md",
    ".txt",
    ".docx",
    ".doc",
)

class VideoProcessingError(Exception):
    """视频处理专用异常类"""
    pass

class APIError(Exception):
    """API调用异常类；retryable=False 表示重试无济于事（如缺少配置）。"""
    def __init__(self, message: str = "", *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable

class FileProcessingError(Exception):
    """文件处理异常类"""
    pass

def ensure_directory_exists(directory: str) -> None:
    """确保目录存在，如不存在则创建"""
    Path(directory).mkdir(parents=True, exist_ok=True)
    logger.debug(f"确保目录存在: {directory}")

def safe_file_operation(operation: str, file_path: str, operation_func, *args, **kwargs):
    """安全的文件操作包装器，统一错误处理"""
    try:
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


def load_json_file(file_path: str) -> Dict[str, Any]:
    """安全地加载JSON文件"""
    def _load():
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"JSON文件已加载: {file_path}")
        return data
    
    return safe_file_operation("加载JSON", file_path, _load)

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
        is_directory = os.path.isdir(file_path)
        return {
            "path": file_path,
            "name": os.path.basename(file_path),
            "size": stat.st_size,
            "size_formatted": "-" if is_directory else format_file_size(stat.st_size),
            "modified_time": datetime.datetime.fromtimestamp(stat.st_mtime),
            "extension": "" if is_directory else Path(file_path).suffix.lower(),
            "is_directory": is_directory,
        }
    
    return safe_file_operation("获取文件信息", file_path, _get_info)

def project_name_sort_key(project: Dict[str, Any]) -> tuple:
    """按项目文件夹名前缀数字排序，非数字名称排在数字项目之后。"""
    name = str(project.get("name", ""))
    match = re.match(r"^(\d+)(?:\.|$)", name)
    if match:
        return (0, int(match.group(1)), name.lower())
    return (1, name.lower())

def _error_chain(error: BaseException):
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        yield error
        error = error.__cause__ or error.__context__


def http_status(error: BaseException) -> int | None:
    """在异常及其包装链上查找 HTTP 状态码（google-genai、openai、requests 各自命名不同）。"""
    for item in _error_chain(error):
        response = getattr(item, "response", None)
        for value in (getattr(item, "code", None), getattr(item, "status_code", None),
                      getattr(response, "status_code", None)):
            if isinstance(value, int) and not isinstance(value, bool) and 100 <= value < 600:
                return value
    return None


def is_retryable(error: BaseException) -> bool:
    """限流（429）、超时和服务端错误（5xx）稍后可能成功；其余 4xx（密钥无效、模型不存在等）及缺少配置重试也无用。"""
    if any(getattr(item, "retryable", True) is False for item in _error_chain(error)):
        return False
    status = http_status(error)
    return status is None or status in (408, 429) or status >= 500


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, max_delay: float = 60.0):
    """重试装饰器：首次失败后最多再试 max_retries 次，等待时间从 delay 起指数增长（上限 max_delay）。"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if not is_retryable(e):
                        logger.error(f"函数 {func.__name__} 失败且不可重试: {e}")
                        raise
                    if attempt == max_retries:
                        logger.error(f"函数 {func.__name__} 重试{max_retries}次后仍然失败")
                        raise
                    wait = min(delay * 2 ** attempt, max_delay) * random.uniform(0.8, 1.2)
                    logger.warning(f"函数 {func.__name__} 第{attempt + 1}次尝试失败: {e}，{wait:.0f}秒后重试（{attempt + 1}/{max_retries}）...")
                    time.sleep(wait)
        return wrapper
    return decorator

def handle_video_operation(operation_name: str, critical: bool = False, fallback_value=None):
    """
    视频操作统一错误处理装饰器
    
    Args:
        operation_name: 操作描述，如"开场片段生成"、"字幕添加"
        critical: True=关键操作失败时抛出VideoProcessingError
                 False=可选操作失败时记录警告并返回fallback_value
        fallback_value: 非关键操作失败时的默认返回值
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                logger.debug(f"{operation_name}完成")
                return result
            except Exception as e:
                if critical:
                    logger.error(f"{operation_name}失败: {str(e)}")
                    raise VideoProcessingError(f"{operation_name}失败: {str(e)}")
                else:
                    logger.warning(f"{operation_name}失败: {str(e)}，使用降级处理")
                    try:
                        # 若提供的是可调用的回退函数，则用相同参数调用以生成回退结果
                        if callable(fallback_value):
                            return fallback_value(*args, **kwargs)
                        # 否则直接返回静态回退值
                        return fallback_value
                    except Exception as fallback_error:
                        logger.warning(f"降级处理函数执行失败: {fallback_error}")
                        return fallback_value
        return wrapper
    return decorator

# 导出主要函数和类
__all__ = [
    'VideoProcessingError', 'APIError', 'FileProcessingError',
    'ensure_directory_exists', 'load_json_file', 'format_file_size',
    'get_file_info', 'http_status', 'is_retryable', 'retry_on_failure', 'handle_video_operation', 'logger',
]
