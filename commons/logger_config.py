import os
import sys
from loguru import logger

class LoggerConfig:
    """
    日志配置类，用于统一管理日志配置
    """
    
    def __init__(self, log_dir="logs", log_level="WARNING"):
        """
        初始化日志配置
        
        Args:
            log_dir (str): 日志目录
            log_level (str): 日志级别，可选值：DEBUG, INFO, WARNING, ERROR, CRITICAL
        """
        # 使用项目根目录作为基础路径
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.log_dir = os.path.join(project_root, log_dir)
        self.log_level = log_level
        
        # 确保日志目录存在
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 移除默认的日志配置
        logger.remove()
        
        # 配置控制台日志
        self._config_console_logger()
        
        # 配置文件日志
        self._config_file_logger()
        
    def _config_console_logger(self):
        """
        配置控制台日志
        """
        # 控制台日志格式
        console_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> <level>{level: <8}</level> <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <magenta>{extra[region]}</magenta> - <level>{message}</level>"
        
        # 只有当sys.stdout不为None时才添加控制台日志（避免PyInstaller窗口模式下的错误）
        if sys.stdout is not None:
            # 添加控制台日志
            logger.add(
                sys.stdout,
                format=console_format,
                level=self.log_level,
                enqueue=True,  # 启用异步写入，提高性能
                backtrace=True,  # 显示完整的调用堆栈
                diagnose=True,  # 显示诊断信息
                colorize=True,  # 启用彩色输出
                encoding='utf-8',
                errors='replace'
            )
    
    def _config_file_logger(self):
        """
        配置文件日志
        """
        # 文件日志格式，包含更多上下文信息
        file_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {extra[region]} | {process.name}:{process.id} | {thread.name}:{thread.id} | {message}"
        
        # 主日志文件
        logger.add(
            os.path.join(self.log_dir, "trading_bot.log"),
            format=file_format,
            level="DEBUG",  # 文件日志记录所有级别
            rotation="500 MB",  # 日志文件达到500MB时轮转
            compression="zip",  # 压缩旧日志文件
            retention="30 days",  # 保留30天的日志
            enqueue=True,  # 启用异步写入，提高性能
            backtrace=True,  # 显示完整的调用堆栈
            diagnose=True,  # 显示诊断信息
            encoding='utf-8',
            errors='replace'
        )
        
        # 错误日志文件，仅记录ERROR和CRITICAL级别
        logger.add(
            os.path.join(self.log_dir, "trading_bot_error.log"),
            format=file_format,
            level="ERROR",  # 仅记录ERROR和CRITICAL
            rotation="100 MB",  # 错误日志文件达到100MB时轮转
            compression="zip",  # 压缩旧日志文件
            retention="90 days",  # 错误日志保留90天
            enqueue=True,  # 启用异步写入，提高性能
            backtrace=True,  # 显示完整的调用堆栈
            diagnose=True,  # 显示诊断信息
            encoding='utf-8',
            errors='replace'
        )
    
    def get_logger(self, name=None, region=None):
        """
        获取日志记录器
        
        Args:
            name (str, optional): 日志记录器名称
            region (str, optional): 日志区域名称
            
        Returns:
            loguru.Logger: 日志记录器
        """
        if name and region:
            return logger.bind(module=name, region=region)
        elif name:
            return logger.bind(module=name, region="Default")
        elif region:
            return logger.bind(region=region)
        return logger.bind(region="Default")
    
    def set_level(self, level):
        """
        设置日志级别
        
        Args:
            level (str): 日志级别，可选值：DEBUG, INFO, WARNING, ERROR, CRITICAL
        """
        self.log_level = level
        # 只有当sys.stdout不为None时才配置控制台日志级别
        if sys.stdout is not None:
            logger.configure(handlers=[{
                "sink": sys.stdout,
                "level": level
            }])

# 创建全局日志配置实例
global_logger_config = LoggerConfig()

# 获取全局日志记录器
global_logger = global_logger_config.get_logger()

# 全局 get_logger 函数，方便其他模块直接使用
def get_logger(name=None, region=None):
    """
    获取日志记录器
    
    Args:
        name (str, optional): 日志记录器名称
        region (str, optional): 日志区域名称
        
    Returns:
        loguru.Logger: 日志记录器
    """
    return global_logger_config.get_logger(name, region)
