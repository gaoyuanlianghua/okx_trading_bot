# network/network_errors.py
"""
网络错误处理模块
"""

import time
from commons.logger_config import global_logger as logger


# 网络错误分类
class NetworkError(Exception):
    """网络错误基类"""
    pass


class ConnectionError(NetworkError):
    """连接错误"""
    pass


class TimeoutError(NetworkError):
    """超时错误"""
    pass


class DNSResolutionError(NetworkError):
    """DNS解析错误"""
    pass


class SSLHandshakeError(NetworkError):
    """SSL握手错误"""
    pass


class RateLimitError(NetworkError):
    """速率限制错误"""
    pass


class ServerError(NetworkError):
    """服务器错误"""
    pass


# 网络错误映射
ERROR_MAPPING = {
    'ConnectionResetError': ConnectionError,
    'ConnectionRefusedError': ConnectionError,
    'TimeoutError': TimeoutError,
    'socket.timeout': TimeoutError,
    'requests.exceptions.Timeout': TimeoutError,
    'socket.gaierror': DNSResolutionError,
    'ssl.SSLError': SSLHandshakeError,
    'requests.exceptions.SSLError': SSLHandshakeError,
    '429': RateLimitError,
    '500': ServerError,
    '502': ServerError,
    '503': ServerError,
    '504': ServerError,
}


class NetworkErrorHandler:
    """网络错误处理器，用于统一处理和统计网络错误"""
    
    def __init__(self):
        self.error_stats = {
            'total_errors': 0,
            'error_types': {},  # {error_type: count}
            'error_history': [],  # 错误历史记录
            'last_error_time': {},  # {error_type: last_time}
            'recovery_success': 0,
            'recovery_failed': 0
        }
        self.error_history_limit = 1000
        self.recovery_strategies = {}
        logger.info("网络错误处理器初始化完成")
    
    def register_recovery_strategy(self, error_type, strategy):
        """
        注册错误恢复策略
        
        Args:
            error_type (class): 错误类型
            strategy (callable): 恢复策略函数
        """
        self.recovery_strategies[error_type] = strategy
        logger.info(f"注册错误恢复策略: {error_type.__name__}")
    
    def handle_error(self, error, context=None):
        """
        处理网络错误
        
        Args:
            error (Exception): 错误对象
            context (dict): 错误上下文信息
            
        Returns:
            bool: 是否成功恢复
        """
        error_type = type(error).__name__
        error_class = ERROR_MAPPING.get(error_type, NetworkError)
        
        # 更新错误统计
        self.error_stats['total_errors'] += 1
        self.error_stats['error_types'][error_type] = self.error_stats['error_types'].get(error_type, 0) + 1
        self.error_stats['last_error_time'][error_type] = time.time()
        
        # 记录错误历史
        error_record = {
            'timestamp': time.time(),
            'error_type': error_type,
            'error_message': str(error),
            'context': context
        }
        self.error_stats['error_history'].append(error_record)
        
        # 限制历史记录大小
        if len(self.error_stats['error_history']) > self.error_history_limit:
            self.error_stats['error_history'] = self.error_stats['error_history'][-self.error_history_limit:]
        
        logger.error(f"网络错误: {error_type} - {error}, 上下文: {context}")
        
        # 尝试恢复
        recovery_strategy = self.recovery_strategies.get(error_class)
        if recovery_strategy:
            try:
                success = recovery_strategy(error, context)
                if success:
                    self.error_stats['recovery_success'] += 1
                    logger.info(f"错误恢复成功: {error_type}")
                    return True
                else:
                    self.error_stats['recovery_failed'] += 1
                    logger.warning(f"错误恢复失败: {error_type}")
            except Exception as e:
                self.error_stats['recovery_failed'] += 1
                logger.error(f"执行恢复策略失败: {e}")
        
        return False
    
    def get_error_stats(self):
        """
        获取错误统计信息
        
        Returns:
            dict: 错误统计信息
        """
        return self.error_stats.copy()
    
    def get_error_rate(self, error_type=None, time_window=300):
        """
        计算错误率
        
        Args:
            error_type (str): 错误类型，None表示所有错误
            time_window (int): 时间窗口，单位秒
            
        Returns:
            float: 错误率
        """
        current_time = time.time()
        window_start = current_time - time_window
        
        if error_type:
            recent_errors = [e for e in self.error_stats['error_history'] 
                           if e['error_type'] == error_type and e['timestamp'] >= window_start]
        else:
            recent_errors = [e for e in self.error_stats['error_history'] 
                           if e['timestamp'] >= window_start]
        
        return len(recent_errors) / time_window if time_window > 0 else 0


# 全局网络错误处理器实例
global_network_error_handler = NetworkErrorHandler()
