"""
统一错误处理模块，定义标准的异常类型和错误处理流程
"""

import time
from commons.logger_config import get_logger
import traceback
import functools
from enum import Enum

logger = get_logger(region="Error")


class ErrorLevel(Enum):
    """错误级别枚举"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class TradingBotError(Exception):
    """交易机器人基础异常类"""
    
    def __init__(self, message, error_code=None, error_level=ErrorLevel.ERROR):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.error_level = error_level
        self.traceback = traceback.format_exc() if error_level in [ErrorLevel.ERROR, ErrorLevel.CRITICAL] else None


class NetworkError(TradingBotError):
    """网络错误异常"""
    
    def __init__(self, message, error_code="NETWORK_ERROR"):
        super().__init__(message, error_code, ErrorLevel.ERROR)


class APIError(TradingBotError):
    """API错误异常"""
    
    def __init__(self, message, error_code="API_ERROR", http_status=None):
        super().__init__(message, error_code, ErrorLevel.ERROR)
        self.http_status = http_status


class ValidationError(TradingBotError):
    """参数验证错误异常"""
    
    def __init__(self, message, error_code="VALIDATION_ERROR"):
        super().__init__(message, error_code, ErrorLevel.WARNING)


class ConfigurationError(TradingBotError):
    """配置错误异常"""
    
    def __init__(self, message, error_code="CONFIG_ERROR"):
        super().__init__(message, error_code, ErrorLevel.CRITICAL)


class ResourceError(TradingBotError):
    """资源错误异常"""
    
    def __init__(self, message, error_code="RESOURCE_ERROR"):
        super().__init__(message, error_code, ErrorLevel.ERROR)


class TradingError(TradingBotError):
    """交易错误异常"""
    
    def __init__(self, message, error_code="TRADING_ERROR", symbol=None):
        super().__init__(message, error_code, ErrorLevel.ERROR)
        self.symbol = symbol


class RiskError(TradingBotError):
    """风险错误异常"""
    
    def __init__(self, message, error_code="RISK_ERROR"):
        super().__init__(message, error_code, ErrorLevel.CRITICAL)


class ErrorHandler:
    """统一错误处理器"""
    
    def __init__(self):
        self.error_counts = {}
        self.recovery_strategies = {}
        self.error_history = []  # 错误历史记录
        self.error_history_limit = 1000  # 错误历史记录上限
        self.error_thresholds = {}  # 错误阈值配置
        self.last_error_time = {}  # 最近错误时间
        logger.info("错误处理器初始化完成")
    
    def log_error(self, error):
        """记录错误日志
        
        Args:
            error (TradingBotError): 错误对象
        """
        # 构建错误日志消息
        log_message = f"[{error.error_code}] {error.message}"
        
        # 根据错误级别记录日志
        if error.error_level == ErrorLevel.CRITICAL:
            logger.critical(log_message)
        elif error.error_level == ErrorLevel.ERROR:
            logger.error(log_message)
        elif error.error_level == ErrorLevel.WARNING:
            logger.warning(log_message)
        else:
            logger.info(log_message)
        
        # 记录详细的堆栈信息（仅ERROR和CRITICAL级别）
        if error.traceback:
            logger.debug(f"错误堆栈:\n{error.traceback}")
        
        # 更新错误统计
        self._update_error_statistics(error)
        
        # 检查错误频率和阈值
        self._check_error_thresholds(error)
    
    def handle_error(self, error, context=None):
        """处理错误并执行恢复策略
        
        Args:
            error (TradingBotError): 错误对象
            context (dict): 错误上下文信息
            
        Returns:
            bool: 是否成功恢复
        """
        # 记录错误
        self.log_error(error)
        
        # 获取恢复策略
        recovery_strategy = self.recovery_strategies.get(error.error_code)
        
        if recovery_strategy:
            try:
                logger.info(f"执行错误恢复策略: {error.error_code}")
                success = recovery_strategy(error, context)
                if success:
                    logger.info(f"错误恢复成功: {error.error_code}")
                    return True
                else:
                    logger.error(f"错误恢复失败: {error.error_code}")
                    return False
            except Exception as e:
                logger.error(f"恢复策略执行失败: {e}")
                return False
        
        # 默认恢复策略
        if error.error_level == ErrorLevel.CRITICAL:
            logger.critical("关键错误，需要人工干预")
            return False
        else:
            logger.info("使用默认恢复策略")
            return True
    
    def register_recovery_strategy(self, error_code, strategy):
        """注册错误恢复策略
        
        Args:
            error_code (str): 错误代码
            strategy (callable): 恢复策略函数
        """
        self.recovery_strategies[error_code] = strategy
        logger.info(f"注册错误恢复策略: {error_code}")
    
    def register_error_threshold(self, error_code, threshold, time_window=60):
        """注册错误阈值
        
        Args:
            error_code (str): 错误代码
            threshold (int): 错误阈值
            time_window (int): 时间窗口（秒）
        """
        self.error_thresholds[error_code] = {
            'threshold': threshold,
            'time_window': time_window
        }
        logger.info(f"注册错误阈值: {error_code}, 阈值: {threshold}, 时间窗口: {time_window}秒")
    
    def get_error_stats(self):
        """获取错误统计信息
        
        Returns:
            dict: 错误统计信息
        """
        return self.error_counts.copy()
    
    def get_error_history(self):
        """获取错误历史记录
        
        Returns:
            list: 错误历史记录
        """
        return self.error_history.copy()
    
    def clear_error_history(self):
        """清空错误历史记录"""
        self.error_history.clear()
        logger.info("错误历史记录已清空")
    
    def _update_error_statistics(self, error):
        """更新错误统计信息
        
        Args:
            error (TradingBotError): 错误对象
        """
        # 更新错误计数
        if error.error_code not in self.error_counts:
            self.error_counts[error.error_code] = 0
        self.error_counts[error.error_code] += 1
        
        # 更新最近错误时间
        self.last_error_time[error.error_code] = time.time()
        
        # 记录错误历史
        error_record = {
            'error_code': error.error_code,
            'message': error.message,
            'level': error.error_level.value,
            'timestamp': time.time(),
            'traceback': error.traceback
        }
        self.error_history.append(error_record)
        
        # 限制错误历史记录数量
        if len(self.error_history) > self.error_history_limit:
            self.error_history.pop(0)
    
    def _check_error_thresholds(self, error):
        """检查错误阈值，触发预警
        
        Args:
            error (TradingBotError): 错误对象
        """
        threshold_config = self.error_thresholds.get(error.error_code)
        if not threshold_config:
            return
        
        threshold = threshold_config['threshold']
        time_window = threshold_config['time_window']
        
        # 检查最近时间窗口内的错误频率
        recent_errors = [e for e in self.error_history 
                        if e['error_code'] == error.error_code 
                        and time.time() - e['timestamp'] <= time_window]
        
        if len(recent_errors) >= threshold:
            logger.warning(f"错误频率超过阈值: {error.error_code}, "
                         f"最近{time_window}秒内发生{len(recent_errors)}次错误，阈值为{threshold}")


def error_handler(return_value=None, re_raise=False):
    """错误处理装饰器
    
    Args:
        return_value: 发生错误时的返回值
        re_raise: 是否重新抛出异常
        
    Returns:
        callable: 装饰后的函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except TradingBotError as e:
                # 使用全局错误处理器
                from .error_handler import global_error_handler
                context = {
                    "function": func.__name__,
                    "args": args,
                    "kwargs": kwargs
                }
                global_error_handler.handle_error(e, context)
                
                if re_raise:
                    raise
                return return_value
            except Exception as e:
                # 将未捕获的异常转换为TradingBotError
                from .error_handler import global_error_handler
                error = TradingBotError(
                    message=f"未捕获的异常: {str(e)}",
                    error_code="UNHANDLED_ERROR",
                    error_level=ErrorLevel.ERROR
                )
                context = {
                    "function": func.__name__,
                    "args": args,
                    "kwargs": kwargs
                }
                global_error_handler.handle_error(error, context)
                
                if re_raise:
                    raise
                return return_value
        return wrapper
    return decorator


def retry(max_attempts=3, delay=1, backoff_factor=2, exceptions=(Exception,)):
    """重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff_factor: 退避因子
        exceptions: 需要重试的异常类型
        
    Returns:
        callable: 装饰后的函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            current_delay = delay
            
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    if attempts >= max_attempts:
                        logger.error(f"函数 {func.__name__} 重试失败，已达到最大重试次数 {max_attempts}")
                        raise
                    
                    logger.warning(f"函数 {func.__name__} 执行失败，{attempts}/{max_attempts}，等待 {current_delay} 秒后重试")
                    import time
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
        return wrapper
    return decorator


# 创建全局错误处理器实例
global_error_handler = ErrorHandler()
