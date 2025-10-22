"""
日志系统
使用 loguru 提供结构化日志
"""
import sys
from pathlib import Path
from loguru import logger
from typing import Optional


def setup_logger(
    log_file: Optional[str] = None,
    level: str = "INFO",
    console: bool = True
) -> None:
    """
    设置日志系统
    
    Args:
        log_file: 日志文件路径
        level: 日志级别
        console: 是否输出到控制台
    """
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台处理器
    if console:
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=level,
            colorize=True
        )
    
    # 添加文件处理器
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=level,
            rotation="100 MB",  # 文件大小超过 100MB 时轮转
            retention="30 days",  # 保留 30 天
            compression="zip"  # 压缩旧日志
        )


def get_logger():
    """
    获取 logger 实例
    
    Returns:
        logger 实例
    """
    return logger

