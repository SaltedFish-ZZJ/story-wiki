"""
Story Wiki - 日志配置模块
统一日志格式和级别，替代分散的 print() 调用。
"""
import logging
import sys


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    配置全局日志并返回项目根 logger。

    Args:
        level: 日志级别，默认 INFO

    Returns:
        配置好的根 logger
    """
    logger = logging.getLogger("story_wiki")

    if logger.handlers:
        return logger

    logger.setLevel(level)

    # 控制台输出
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # 格式：[级别] 模块名 - 消息
    formatter = logging.Formatter(
        fmt="[%(levelname)s] %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # 防止日志向上层传播导致重复输出
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取子 logger。

    Args:
        name: 模块名，如 "analyzer"、"chapter_generator"

    Returns:
        子 logger
    """
    return logging.getLogger(f"story_wiki.{name}")
