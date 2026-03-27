# network/network_monitor.py
"""
网络状态监控模块，用于实时监控网络性能
"""

import time
from threading import Lock

# 初始化日志配置
from commons.logger_config import global_logger_config

# 获取区域化日志记录器
def get_logger(region=None):
    return global_logger_config.get_logger(region=region)

# 创建默认日志记录器
logger = get_logger("Network")


class NetworkMonitor:
    """网络状态监控器，用于实时监控网络性能"""
    
    def __init__(self):
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'request_times': [],  # 请求时间列表
            'response_sizes': [],  # 响应大小列表
            'active_connections': 0,
            'max_active_connections': 0,
            'connection_pool_usage': {},  # 连接池使用情况
            'throughput': 0,  # 吞吐量（bytes/sec）
            'last_reset_time': time.time()
        }
        self.metrics_lock = Lock()
        logger.info("网络监控器初始化完成")
    
    def record_request(self, success=True, request_time=0, response_size=0):
        """
        记录请求信息
        
        Args:
            success (bool): 请求是否成功
            request_time (float): 请求耗时（秒）
            response_size (int): 响应大小（字节）
        """
        with self.metrics_lock:
            self.metrics['total_requests'] += 1
            if success:
                self.metrics['successful_requests'] += 1
            else:
                self.metrics['failed_requests'] += 1
            
            if request_time > 0:
                self.metrics['request_times'].append(request_time)
            if response_size > 0:
                self.metrics['response_sizes'].append(response_size)
            
            # 更新吞吐量
            elapsed = time.time() - self.metrics['last_reset_time']
            if elapsed > 0:
                self.metrics['throughput'] = sum(self.metrics['response_sizes']) / elapsed
    
    def update_connection_status(self, active_connections):
        """
        更新连接状态
        
        Args:
            active_connections (int): 当前活跃连接数
        """
        with self.metrics_lock:
            self.metrics['active_connections'] = active_connections
            if active_connections > self.metrics['max_active_connections']:
                self.metrics['max_active_connections'] = active_connections
    
    def update_connection_pool_usage(self, pool_name, usage):
        """
        更新连接池使用情况
        
        Args:
            pool_name (str): 连接池名称
            usage (dict): 使用情况
        """
        with self.metrics_lock:
            self.metrics['connection_pool_usage'][pool_name] = usage
    
    def get_performance_report(self):
        """
        获取性能报告
        
        Returns:
            dict: 性能报告
        """
        with self.metrics_lock:
            metrics = self.metrics.copy()
            
            # 计算统计信息
            request_times = metrics['request_times']
            response_sizes = metrics['response_sizes']
            
            report = {
                'timestamp': time.time(),
                'total_requests': metrics['total_requests'],
                'success_rate': metrics['successful_requests'] / metrics['total_requests'] if metrics['total_requests'] > 0 else 0,
                'avg_response_time': sum(request_times) / len(request_times) if request_times else 0,
                'min_response_time': min(request_times) if request_times else 0,
                'max_response_time': max(request_times) if request_times else 0,
                'avg_response_size': sum(response_sizes) / len(response_sizes) if response_sizes else 0,
                'active_connections': metrics['active_connections'],
                'max_active_connections': metrics['max_active_connections'],
                'throughput': metrics['throughput'],
                'connection_pool_usage': metrics['connection_pool_usage'].copy()
            }
            
            return report
    
    def reset_metrics(self):
        """重置统计指标"""
        with self.metrics_lock:
            self.metrics = {
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'request_times': [],
                'response_sizes': [],
                'active_connections': 0,
                'max_active_connections': 0,
                'connection_pool_usage': {},
                'throughput': 0,
                'last_reset_time': time.time()
            }
            logger.info("网络监控指标已重置")


# 全局网络监控实例
global_network_monitor = NetworkMonitor()
