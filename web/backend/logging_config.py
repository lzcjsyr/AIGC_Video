"""
Web后端专用日志配置
配置适合Web服务器的日志格式和输出
"""

import logging
from pathlib import Path


def setup_web_logging(log_level=logging.INFO):
    """配置Web后端专用的日志设置"""
    
    # 清除可能存在的旧配置
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Web日志保存到web/backend目录下
    web_dir = Path(__file__).parent
    log_file = web_dir / 'web.log'
    
    # 配置日志格式（Web服务器友好的格式，包含进程ID）
    import os
    logging.basicConfig(
        level=log_level,
        format=f'%(asctime)s [WEB:{os.getpid()}] %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # 控制台输出
        ]
    )
    
    # 设置AIGC_Video logger
    logger = logging.getLogger('AIGC_Video')
    logger.setLevel(log_level)
    
    # 降低第三方库的噪声日志
    for lib_name in [
        "pdfminer", "pdfminer.pdffont", "pdfminer.pdfinterp", "pdfminer.cmapdb",
        "urllib3", "requests", "PIL", "werkzeug", "socketio", "engineio"
    ]:
        logging.getLogger(lib_name).setLevel(logging.ERROR)
    
    # Web特有的日志级别调整
    logging.getLogger('werkzeug').setLevel(logging.WARNING)  # Flask内置服务器日志
    
    logger.info("Web后端日志配置完成")
    return logger