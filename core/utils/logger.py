"""
日志配置模块

提供更详细的错误信息和调试信息，支持日志轮转和结构化日志
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional


class LoggerConfig:
    """日志配置类"""
    
    def __init__(self, log_dir: str = "logs"):
        """
        初始化日志配置
        
        Args:
            log_dir: 日志目录
        """
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        
    def get_formatter(self, structured: bool = False) -> logging.Formatter:
        """
        获取日志格式化器
        
        Args:
            structured: 是否使用结构化日志格式
            
        Returns:
            logging.Formatter: 日志格式化器
        """
        if structured:
            return logging.Formatter(
                '{'
                '"timestamp": "%(asctime)s", '
                '"level": "%(levelname)s", '
                '"logger": "%(name)s", '
                '"module": "%(module)s", '
                '"function": "%(funcName)s", '
                '"line": %(lineno)d, '
                '"message": "%(message)s", '
                '"process": %(process)d, '
                '"thread": %(thread)d'
                '}'
            )
        else:
            return logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s'
            )
    
    def configure(self, level: int = logging.INFO, structured: bool = False):
        """
        配置日志系统
        
        Args:
            level: 日志级别
            structured: 是否使用结构化日志格式
        """
        # 根日志配置
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # 清除现有处理器
        root_logger.handlers.clear()
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(self.get_formatter(structured))
        root_logger.addHandler(console_handler)
        
        # 信息日志文件处理器（按天轮转）
        info_handler = TimedRotatingFileHandler(
            os.path.join(self.log_dir, "info.log"),
            when="D",
            interval=1,
            backupCount=7,
            encoding="utf-8"
        )
        info_handler.setLevel(logging.INFO)
        info_handler.setFormatter(self.get_formatter(structured))
        info_handler.addFilter(lambda record: record.levelno == logging.INFO)
        root_logger.addHandler(info_handler)
        
        # 错误日志文件处理器（按大小轮转）
        error_handler = RotatingFileHandler(
            os.path.join(self.log_dir, "error.log"),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(self.get_formatter(structured))
        root_logger.addHandler(error_handler)
        
        # 调试日志文件处理器（按大小轮转）
        debug_handler = RotatingFileHandler(
            os.path.join(self.log_dir, "debug.log"),
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=3,
            encoding="utf-8"
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(self.get_formatter(structured))
        root_logger.addHandler(debug_handler)
        
        return root_logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取日志记录器
    
    Args:
        name: 日志名称
        
    Returns:
        logging.Logger: 日志记录器
    """
    return logging.getLogger(name)


# 全局日志配置实例
logger_config = LoggerConfig()
