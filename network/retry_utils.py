# network/retry_utils.py
"""
重试装饰器模块
"""

import time
import functools
from commons.logger_config import global_logger as logger
from .network_errors import ERROR_MAPPING, NetworkError, ConnectionError, TimeoutError, DNSResolutionError, SSLHandshakeError, RateLimitError


def smart_retry(max_retries=3, backoff_factor=0.1):
    """
    智能重试装饰器，根据错误类型采用不同的重试策略
    
    Args:
        max_retries (int): 最大重试次数
        backoff_factor (float): 退避因子
        
    Returns:
        function: 装饰后的函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retry_count = 0
            
            while retry_count <= max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # 分类错误
                    error_type = type(e).__name__
                    error_class = ERROR_MAPPING.get(error_type, NetworkError)
                    
                    # 根据错误类型决定重试策略
                    if isinstance(e, (ConnectionError, TimeoutError)):
                        # 连接和超时错误，重试次数较多
                        max_allowed_retries = max_retries * 2
                    elif isinstance(e, (DNSResolutionError, SSLHandshakeError)):
                        # DNS和SSL错误，重试次数较少
                        max_allowed_retries = max_retries // 2
                    elif isinstance(e, RateLimitError):
                        # 速率限制错误，增加退避时间
                        max_allowed_retries = max_retries
                        backoff_factor *= 2
                    else:
                        # 其他错误，标准重试
                        max_allowed_retries = max_retries
                    
                    retry_count += 1
                    
                    if retry_count > max_allowed_retries:
                        logger.error(f"函数 {func.__name__} 执行失败，已达到最大重试次数: {max_allowed_retries}")
                        raise error_class(f"{e}") from e
                    
                    # 计算退避时间
                    backoff_time = backoff_factor * (2 ** (retry_count - 1))
                    logger.warning(f"函数 {func.__name__} 执行失败: {e}, 将在 {backoff_time:.2f}秒后重试 (第 {retry_count}/{max_allowed_retries} 次)")
                    
                    time.sleep(backoff_time)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def retry_with_backoff(max_retries=3, initial_delay=0.5, backoff_factor=2, exceptions=(Exception,)):
    """
    重试装饰器，支持指数退避策略
    
    Args:
        max_retries (int): 最大重试次数
        initial_delay (float): 初始延迟（秒）
        backoff_factor (float): 退避因子
        exceptions (tuple): 要捕获并重试的异常类型
    
    Returns:
        function: 装饰后的函数
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"重试次数耗尽，函数 {func.__name__} 执行失败: {e}")
                        raise
                    logger.warning(f"函数 {func.__name__} 执行失败（尝试 {attempt+1}/{max_retries+1}）: {e}")
                    logger.info(f"{delay} 秒后重试...")
                    time.sleep(delay)
                    delay *= backoff_factor
        return wrapper
    return decorator
