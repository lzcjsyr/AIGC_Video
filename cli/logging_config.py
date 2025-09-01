"""
CLI专用日志配置
配置适合命令行界面的日志格式和输出
"""

import logging
from pathlib import Path


def setup_cli_logging(log_level=logging.INFO):
    """配置CLI专用的日志设置"""
    
    # 清除可能存在的旧配置
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # CLI日志保存到cli目录下
    cli_dir = Path(__file__).parent
    log_file = cli_dir / 'cli.log'
    
    # 配置日志格式（CLI友好的简洁格式）
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [CLI] %(levelname)s - %(message)s',
        datefmt='%H:%M:%S',
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
        "urllib3", "requests", "PIL"
    ]:
        logging.getLogger(lib_name).setLevel(logging.ERROR)
    
    logger.info("CLI日志配置完成")
    return logger