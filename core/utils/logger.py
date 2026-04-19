"""
日志配置模块

提供更详细的错误信息和调试信息，支持日志轮转和结构化日志
"""

import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional, List, Tuple


class LoggerConfig:
    """日志配置类"""
    
    def __init__(self, log_dir: str = "logs", max_total_size_gb: float = 5.0):
        """
        初始化日志配置
        
        Args:
            log_dir: 日志目录
            max_total_size_gb: 日志总大小限制（GB）
        """
        self.log_dir = log_dir
        self.max_total_size_gb = max_total_size_gb
        self.max_total_size_bytes = max_total_size_gb * 1024 * 1024 * 1024
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
        # 清理旧日志
        self.clean_old_logs()
        
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
        
        # 分类日志处理器
        self._add_category_handlers(root_logger, level, structured)
        
        return root_logger
    
    def _add_category_handlers(self, root_logger: logging.Logger, level: int, structured: bool):
        """
        添加分类日志处理器
        
        Args:
            root_logger: 根日志记录器
            level: 日志级别
            structured: 是否使用结构化日志格式
        """
        # 策略信号日志
        strategy_handler = TimedRotatingFileHandler(
            os.path.join(self.log_dir, "strategy", "strategy.log"),
            when="D",
            interval=1,
            backupCount=7,
            encoding="utf-8"
        )
        strategy_handler.setLevel(logging.INFO)
        strategy_handler.setFormatter(self.get_formatter(structured))
        strategy_handler.addFilter(lambda record: "策略信号" in record.getMessage() or "signal" in record.getMessage().lower())
        root_logger.addHandler(strategy_handler)
        
        # 风险警报日志
        risk_handler = TimedRotatingFileHandler(
            os.path.join(self.log_dir, "risk", "risk.log"),
            when="D",
            interval=1,
            backupCount=7,
            encoding="utf-8"
        )
        risk_handler.setLevel(logging.WARNING)
        risk_handler.setFormatter(self.get_formatter(structured))
        risk_handler.addFilter(lambda record: "风险" in record.getMessage() or "risk" in record.getMessage().lower())
        root_logger.addHandler(risk_handler)
        
        # 交易信号日志
        trade_handler = TimedRotatingFileHandler(
            os.path.join(self.log_dir, "trade", "trade.log"),
            when="D",
            interval=1,
            backupCount=7,
            encoding="utf-8"
        )
        trade_handler.setLevel(logging.INFO)
        trade_handler.setFormatter(self.get_formatter(structured))
        trade_handler.addFilter(lambda record: "平仓" in record.getMessage() or "交易" in record.getMessage() or "trade" in record.getMessage().lower())
        root_logger.addHandler(trade_handler)
        
        # 系统状态日志
        system_handler = TimedRotatingFileHandler(
            os.path.join(self.log_dir, "system", "system.log"),
            when="D",
            interval=1,
            backupCount=7,
            encoding="utf-8"
        )
        system_handler.setLevel(logging.INFO)
        system_handler.setFormatter(self.get_formatter(structured))
        system_handler.addFilter(lambda record: "启动" in record.getMessage() or "初始化" in record.getMessage() or "系统" in record.getMessage() or "system" in record.getMessage().lower())
        root_logger.addHandler(system_handler)
        
        # API调用日志
        api_handler = TimedRotatingFileHandler(
            os.path.join(self.log_dir, "api", "api.log"),
            when="D",
            interval=1,
            backupCount=7,
            encoding="utf-8"
        )
        api_handler.setLevel(logging.INFO)
        api_handler.setFormatter(self.get_formatter(structured))
        api_handler.addFilter(lambda record: "API" in record.getMessage() or "api" in record.getMessage().lower())
        root_logger.addHandler(api_handler)
    
    def get_log_total_size(self) -> int:
        """
        计算日志目录的总大小（字节）
        
        Returns:
            int: 总大小（字节）
        """
        total_size = 0
        for root, dirs, files in os.walk(self.log_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
        return total_size
    
    def get_all_log_files(self) -> List[Tuple[str, float]]:
        """
        获取所有日志文件及其修改时间
        
        Returns:
            List[Tuple[str, float]]: 日志文件路径和修改时间的列表
        """
        log_files = []
        for root, dirs, files in os.walk(self.log_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    mtime = os.path.getmtime(file_path)
                    log_files.append((file_path, mtime))
        # 按修改时间排序，最旧的在前
        log_files.sort(key=lambda x: x[1])
        return log_files
    
    def clean_old_logs(self):
        """
        清理旧日志文件，确保总大小不超过限制
        """
        total_size = self.get_log_total_size()
        
        if total_size <= self.max_total_size_bytes:
            return
        
        # 获取所有日志文件，按修改时间排序
        log_files = self.get_all_log_files()
        
        # 逐个删除最旧的文件，直到总大小符合要求
        for file_path, _ in log_files:
            if total_size <= self.max_total_size_bytes:
                break
            
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                os.remove(file_path)
                total_size -= file_size
                # 使用print而不是logging，避免递归调用
                print(f"删除旧日志文件: {file_path}, 释放空间: {file_size / (1024 * 1024):.2f}MB")


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
