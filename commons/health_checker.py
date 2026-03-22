import time
import threading
from typing import Dict, Any, List
from loguru import logger

class HealthChecker:
    """
    健康检查类，用于定期检查系统的健康状态
    """
    
    def __init__(self, check_interval=60, min_interval=10, max_interval=300):
        """
        初始化健康检查器
        
        Args:
            check_interval (int): 检查间隔，单位秒，默认60秒
            min_interval (int): 最小检查间隔，单位秒，默认10秒
            max_interval (int): 最大检查间隔，单位秒，默认300秒（5分钟）
        """
        self.base_interval = check_interval  # 基础检查间隔
        self.check_interval = check_interval  # 当前检查间隔
        self.min_interval = min_interval  # 最小检查间隔
        self.max_interval = max_interval  # 最大检查间隔
        self.is_running = False
        self._lock = threading.RLock()
        self._check_thread = None
        self.last_adjustment_time = time.time()  # 上次调整检查间隔的时间
        self.adjustment_cooldown = 300  # 调整冷却时间，单位秒（5分钟）
        
        # 健康状态存储
        self.health_status = {
            'timestamp': time.time(),
            'overall': 'UNKNOWN',  # UNKNOWN, HEALTHY, DEGRADED, CRITICAL
            'checks': {
                'network': {
                    'status': 'UNKNOWN',  # UNKNOWN, PASS, FAIL
                    'message': '',
                    'latency': 0.0
                },
                'api': {
                    'status': 'UNKNOWN',
                    'message': '',
                    'latency': 0.0,
                    'last_response_time': 0.0
                },
                'websocket': {
                    'status': 'UNKNOWN',
                    'message': '',
                    'connected_channels': [],
                    'last_message_time': 0.0
                },
                'services': {
                    'status': 'UNKNOWN',
                    'message': '',
                    'running_services': [],
                    'stopped_services': []
                },
                'memory': {
                    'status': 'UNKNOWN',
                    'message': '',
                    'used': 0,
                    'total': 0,
                    'percent': 0.0
                },
                'disk': {
                    'status': 'UNKNOWN',
                    'message': '',
                    'used': 0,
                    'total': 0,
                    'percent': 0.0
                }
            }
        }
        
        # 健康检查钩子
        self.health_check_hooks: List[callable] = []
    
    def start(self):
        """
        启动健康检查
        """
        with self._lock:
            if self.is_running:
                logger.warning("健康检查已经在运行中")
                return
            
            self.is_running = True
            self._check_thread = threading.Thread(target=self._run_checks, daemon=True, name="HealthChecker")
            self._check_thread.start()
            logger.info(f"健康检查已启动，检查间隔: {self.check_interval}秒")
    
    def stop(self):
        """
        停止健康检查
        """
        with self._lock:
            if not self.is_running:
                logger.warning("健康检查已经停止")
                return
            
            self.is_running = False
            if self._check_thread:
                self._check_thread.join(timeout=5.0)
                self._check_thread = None
            logger.info("健康检查已停止")
    
    def _run_checks(self):
        """
        运行健康检查
        """
        while self.is_running:
            try:
                # 执行健康检查
                self._perform_checks()
                
                # 动态调整检查间隔
                self._adjust_check_interval()
                
                # 等待检查间隔
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"健康检查执行失败: {e}")
                # 发生错误时，使用最小检查间隔
                time.sleep(self.min_interval)
    
    def _perform_checks(self):
        """
        执行具体的健康检查
        """
        # 更新时间戳
        self.health_status['timestamp'] = time.time()
        
        # 执行系统健康检查
        self._check_system_health()
        
        # 执行自定义健康检查钩子
        self._run_custom_checks()
        
        # 更新整体健康状态
        self._update_overall_status()
        
        # 记录健康状态
        self._log_health_status()
    
    def _check_system_health(self):
        """
        检查系统健康状态，包括内存和磁盘使用情况
        """
        try:
            import psutil
            
            # 检查内存使用情况
            memory = psutil.virtual_memory()
            self.health_status['checks']['memory'] = {
                'status': 'PASS' if memory.percent < 90 else 'FAIL',
                'message': f"内存使用率: {memory.percent}%",
                'used': memory.used,
                'total': memory.total,
                'percent': memory.percent
            }
            
            # 检查磁盘使用情况
            disk = psutil.disk_usage('/')
            self.health_status['checks']['disk'] = {
                'status': 'PASS' if disk.percent < 90 else 'FAIL',
                'message': f"磁盘使用率: {disk.percent}%",
                'used': disk.used,
                'total': disk.total,
                'percent': disk.percent
            }
        except ImportError:
            logger.warning("psutil库未安装，无法执行系统健康检查")
            self.health_status['checks']['memory'] = {
                'status': 'UNKNOWN',
                'message': 'psutil库未安装',
                'used': 0,
                'total': 0,
                'percent': 0.0
            }
            self.health_status['checks']['disk'] = {
                'status': 'UNKNOWN',
                'message': 'psutil库未安装',
                'used': 0,
                'total': 0,
                'percent': 0.0
            }
        except Exception as e:
            logger.error(f"系统健康检查失败: {e}")
    
    def _run_custom_checks(self):
        """
        运行自定义健康检查钩子
        """
        for hook in self.health_check_hooks:
            try:
                hook(self)
            except Exception as e:
                logger.error(f"自定义健康检查钩子执行失败: {e}")
    
    def _update_overall_status(self):
        """
        更新整体健康状态
        """
        # 统计各检查的状态
        pass_count = 0
        fail_count = 0
        unknown_count = 0
        
        for check_name, check_result in self.health_status['checks'].items():
            if check_result['status'] == 'PASS':
                pass_count += 1
            elif check_result['status'] == 'FAIL':
                fail_count += 1
            else:
                unknown_count += 1
        
        # 计算整体健康状态
        if fail_count > 0:
            self.health_status['overall'] = 'CRITICAL'
        elif unknown_count > 0:
            self.health_status['overall'] = 'DEGRADED'
        else:
            self.health_status['overall'] = 'HEALTHY'
    
    def _log_health_status(self):
        """
        记录健康状态
        """
        overall = self.health_status['overall']
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.health_status['timestamp']))
        
        logger.info(f"健康检查报告 [{timestamp}]: 整体状态={overall}, 检查间隔={self.check_interval}秒")
        
        for check_name, check_result in self.health_status['checks'].items():
            status = check_result['status']
            message = check_result['message']
            logger.info(f"  {check_name}: {status} - {message}")
    
    def _adjust_check_interval(self):
        """
        根据系统健康状态动态调整检查间隔
        """
        current_time = time.time()
        
        # 检查是否在冷却期内
        if current_time - self.last_adjustment_time < self.adjustment_cooldown:
            return
        
        overall_status = self.health_status['overall']
        new_interval = self.base_interval
        
        # 根据健康状态调整检查间隔
        if overall_status == 'CRITICAL':
            # 系统严重问题，使用最小检查间隔
            new_interval = self.min_interval
        elif overall_status == 'DEGRADED':
            # 系统降级，缩短检查间隔
            new_interval = max(self.min_interval, int(self.base_interval * 0.5))
        elif overall_status == 'HEALTHY':
            # 系统健康，可以延长检查间隔
            new_interval = min(self.max_interval, int(self.base_interval * 1.5))
        
        # 如果检查间隔发生变化，更新并记录
        if new_interval != self.check_interval:
            old_interval = self.check_interval
            self.check_interval = new_interval
            self.last_adjustment_time = current_time
            logger.info(f"动态调整健康检查间隔: {old_interval}秒 -> {new_interval}秒 (系统状态: {overall_status})")
    
    def add_check_hook(self, hook):
        """
        添加自定义健康检查钩子
        
        Args:
            hook (callable): 健康检查钩子函数，接收HealthChecker实例作为参数
        """
        with self._lock:
            if hook not in self.health_check_hooks:
                self.health_check_hooks.append(hook)
    
    def remove_check_hook(self, hook):
        """
        移除自定义健康检查钩子
        
        Args:
            hook (callable): 要移除的健康检查钩子函数
        """
        with self._lock:
            if hook in self.health_check_hooks:
                self.health_check_hooks.remove(hook)
    
    def update_check_status(self, check_name, status, message, **kwargs):
        """
        更新指定检查的状态
        
        Args:
            check_name (str): 检查名称
            status (str): 检查状态，可选值: UNKNOWN, PASS, FAIL
            message (str): 检查消息
            **kwargs: 其他检查结果数据
        """
        with self._lock:
            if check_name not in self.health_status['checks']:
                self.health_status['checks'][check_name] = {
                    'status': status,
                    'message': message
                }
            else:
                self.health_status['checks'][check_name]['status'] = status
                self.health_status['checks'][check_name]['message'] = message
            
            # 更新其他检查结果数据
            for key, value in kwargs.items():
                self.health_status['checks'][check_name][key] = value
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        获取当前健康状态
        
        Returns:
            Dict[str, Any]: 健康状态信息
        """
        with self._lock:
            return self.health_status.copy()
    
    def is_healthy(self) -> bool:
        """
        检查系统是否健康
        
        Returns:
            bool: 系统是否健康
        """
        with self._lock:
            return self.health_status['overall'] in ['HEALTHY', 'DEGRADED']

# 创建全局健康检查实例
global_health_checker = HealthChecker()
