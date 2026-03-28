import os
import sys
from loguru import logger
from collections import defaultdict

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
        
        # 日志缓冲区，按区域分组
        self.log_buffer = defaultdict(list)
        self.buffer_size = 3  # 每3-5行显示一次
        
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
        # 自定义日志处理器，实现按区域分组显示
        def grouped_log_handler(message):
            # 获取日志区域
            region = message.record["extra"].get("region", "Default")
            
            # 将日志消息添加到对应区域的缓冲区
            self.log_buffer[region].append(message)
            
            # 当缓冲区达到指定大小时，批量显示
            if len(self.log_buffer[region]) >= self.buffer_size:
                # 显示区域标题
                print(f"\n{'='*60}")
                print(f"区域: {region}")
                print(f"{'='*60}")
                
                # 显示该区域的所有日志
                for msg in self.log_buffer[region]:
                    # 格式化日志消息
                    time_str = msg.record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    level_str = msg.record["level"].name
                    name_str = msg.record["name"]
                    function_str = msg.record["function"]
                    line_str = msg.record["line"]
                    message_str = msg.record["message"]
                    
                    # 彩色输出
                    level_color = {
                        "DEBUG": "\033[94m",      # 蓝色
                        "INFO": "\033[92m",       # 绿色
                        "WARNING": "\033[93m",    # 黄色
                        "ERROR": "\033[91m",      # 红色
                        "CRITICAL": "\033[95m"    # 紫色
                    }.get(level_str, "\033[0m")
                    
                    reset_color = "\033[0m"
                    
                    # 打印日志
                    print(f"{level_color}{time_str} {level_str:<8} {name_str}:{function_str}:{line_str} | {region} - {message_str}{reset_color}")
                
                # 清空该区域的缓冲区
                self.log_buffer[region].clear()
        
        # 只有当sys.stdout不为None时才添加控制台日志（避免PyInstaller窗口模式下的错误）
        if sys.stdout is not None:
            # 添加控制台日志
            logger.add(
                grouped_log_handler,
                level=self.log_level,
                enqueue=True,  # 启用异步写入，提高性能
                backtrace=True,  # 显示完整的调用堆栈
                diagnose=True  # 显示诊断信息
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
            diagnose=True  # 显示诊断信息
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
            diagnose=True  # 显示诊断信息
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
    
    def flush_buffers(self):
        """
        刷新所有日志缓冲区，显示剩余的日志
        """
        for region, messages in self.log_buffer.items():
            if messages:
                # 显示区域标题
                print(f"\n{'='*60}")
                print(f"区域: {region} (剩余日志)")
                print(f"{'='*60}")
                
                # 显示该区域的所有日志
                for msg in messages:
                    # 格式化日志消息
                    time_str = msg.record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    level_str = msg.record["level"].name
                    name_str = msg.record["name"]
                    function_str = msg.record["function"]
                    line_str = msg.record["line"]
                    message_str = msg.record["message"]
                    
                    # 彩色输出
                    level_color = {
                        "DEBUG": "\033[94m",      # 蓝色
                        "INFO": "\033[92m",       # 绿色
                        "WARNING": "\033[93m",    # 黄色
                        "ERROR": "\033[91m",      # 红色
                        "CRITICAL": "\033[95m"    # 紫色
                    }.get(level_str, "\033[0m")
                    
                    reset_color = "\033[0m"
                    
                    # 打印日志
                    print(f"{level_color}{time_str} {level_str:<8} {name_str}:{function_str}:{line_str} | {region} - {message_str}{reset_color}")
                
                # 清空该区域的缓冲区
                self.log_buffer[region].clear()

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
