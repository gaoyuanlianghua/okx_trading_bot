import time
import threading
from typing import Dict, Any, List, Optional
from commons.logger_config import get_logger

logger = get_logger(region="Alert")

class AlertManager:
    """
    告警管理类，用于管理系统的告警机制
    """
    
    def __init__(self, alert_interval=60, max_alerts_per_minute=10):
        """
        初始化告警管理器
        
        Args:
            alert_interval (int): 告警检查间隔，单位秒，默认60秒
            max_alerts_per_minute (int): 每分钟最大告警次数，默认10次
        """
        self.alert_interval = alert_interval
        self.max_alerts_per_minute = max_alerts_per_minute
        self.is_running = False
        self._lock = threading.RLock()
        self._alert_thread = None
        
        # 告警历史，用于限流
        self.alert_history = []
        
        # 告警规则
        self.alert_rules = {
            'network': {
                'condition': lambda status: status == 'FAIL',
                'message': '网络连接失败',
                'severity': 'CRITICAL',
                'cooldown': 300  # 5分钟冷却
            },
            'api': {
                'condition': lambda status: status == 'FAIL',
                'message': 'API连接失败',
                'severity': 'CRITICAL',
                'cooldown': 300
            },
            'websocket': {
                'condition': lambda status: status == 'FAIL',
                'message': 'WebSocket连接失败',
                'severity': 'CRITICAL',
                'cooldown': 300
            },
            'memory': {
                'condition': lambda percent: percent > 90,
                'message': '内存使用率过高',
                'severity': 'WARNING',
                'cooldown': 600  # 10分钟冷却
            },
            'disk': {
                'condition': lambda percent: percent > 90,
                'message': '磁盘使用率过高',
                'severity': 'WARNING',
                'cooldown': 600
            }
        }
        
        # 告警通知渠道
        self.notification_channels = []
        
        # 最近的告警状态
        self.last_alert_status = {}
    
    def start(self):
        """
        启动告警管理器
        """
        with self._lock:
            if self.is_running:
                logger.warning("告警管理器已经在运行中")
                return
            
            self.is_running = True
            self._alert_thread = threading.Thread(target=self._run_alerts, daemon=True, name="AlertManager")
            self._alert_thread.start()
            logger.info(f"告警管理器已启动，检查间隔: {self.alert_interval}秒")
    
    def stop(self):
        """
        停止告警管理器
        """
        with self._lock:
            if not self.is_running:
                logger.warning("告警管理器已经停止")
                return
            
            self.is_running = False
            if self._alert_thread:
                self._alert_thread.join(timeout=5.0)
                self._alert_thread = None
            logger.info("告警管理器已停止")
    
    def _run_alerts(self):
        """
        运行告警检查
        """
        while self.is_running:
            try:
                # 执行告警检查
                self._check_alerts()
                
                # 清理过期的告警历史
                self._clean_alert_history()
                
                # 等待检查间隔
                time.sleep(self.alert_interval)
            except Exception as e:
                logger.error(f"告警检查执行失败: {e}")
                # 发生错误时，使用最小检查间隔
                time.sleep(10)
    
    def _check_alerts(self):
        """
        执行具体的告警检查
        """
        try:
            from commons.health_checker import global_health_checker
            health_status = global_health_checker.get_health_status()
            
            # 检查各个系统组件的状态
            for check_name, check_result in health_status['checks'].items():
                if check_name in self.alert_rules:
                    rule = self.alert_rules[check_name]
                    
                    # 检查是否满足告警条件
                    if check_name in ['memory', 'disk']:
                        condition_met = rule['condition'](check_result.get('percent', 0))
                    else:
                        condition_met = rule['condition'](check_result.get('status', 'UNKNOWN'))
                    
                    # 检查是否需要告警
                    if condition_met and self._should_alert(check_name, rule['cooldown']):
                        self._trigger_alert(check_name, rule['message'], rule['severity'], check_result)
        except Exception as e:
            logger.error(f"告警检查失败: {e}")
    
    def _should_alert(self, check_name: str, cooldown: int) -> bool:
        """
        检查是否应该触发告警
        
        Args:
            check_name (str): 检查名称
            cooldown (int): 冷却时间
            
        Returns:
            bool: 是否应该触发告警
        """
        with self._lock:
            # 检查是否在冷却期内
            if check_name in self.last_alert_status:
                last_alert_time = self.last_alert_status[check_name]
                if time.time() - last_alert_time < cooldown:
                    return False
            
            # 检查告警频率是否超过限制
            current_time = time.time()
            recent_alerts = [t for t in self.alert_history if current_time - t < 60]
            if len(recent_alerts) >= self.max_alerts_per_minute:
                logger.warning(f"告警频率超过限制，每分钟最多 {self.max_alerts_per_minute} 次")
                return False
            
            return True
    
    def _trigger_alert(self, check_name: str, message: str, severity: str, details: Dict[str, Any]):
        """
        触发告警
        
        Args:
            check_name (str): 检查名称
            message (str): 告警消息
            severity (str): 告警严重程度
            details (Dict[str, Any]): 告警详情
        """
        with self._lock:
            # 记录告警时间
            current_time = time.time()
            self.last_alert_status[check_name] = current_time
            self.alert_history.append(current_time)
            
            # 构建告警信息
            alert_info = {
                'timestamp': current_time,
                'check_name': check_name,
                'message': message,
                'severity': severity,
                'details': details
            }
            
            # 记录告警
            logger.info(f"[{severity}] 告警: {message} - {check_name}")
            logger.debug(f"告警详情: {alert_info}")
            
            # 发送告警通知
            self._send_notifications(alert_info)
    
    def _send_notifications(self, alert_info: Dict[str, Any]):
        """
        发送告警通知
        
        Args:
            alert_info (Dict[str, Any]): 告警信息
        """
        for channel in self.notification_channels:
            try:
                channel.send(alert_info)
            except Exception as e:
                logger.error(f"发送告警通知失败: {e}")
    
    def _clean_alert_history(self):
        """
        清理过期的告警历史
        """
        with self._lock:
            current_time = time.time()
            # 只保留最近10分钟的告警历史
            self.alert_history = [t for t in self.alert_history if current_time - t < 600]
    
    def add_notification_channel(self, channel):
        """
        添加告警通知渠道
        
        Args:
            channel: 通知渠道对象，必须实现send方法
        """
        with self._lock:
            if channel not in self.notification_channels:
                self.notification_channels.append(channel)
                logger.info("添加告警通知渠道成功")
    
    def remove_notification_channel(self, channel):
        """
        移除告警通知渠道
        
        Args:
            channel: 要移除的通知渠道对象
        """
        with self._lock:
            if channel in self.notification_channels:
                self.notification_channels.remove(channel)
                logger.info("移除告警通知渠道成功")
    
    def add_alert_rule(self, check_name: str, condition, message: str, severity: str, cooldown: int = 300):
        """
        添加告警规则
        
        Args:
            check_name (str): 检查名称
            condition: 告警条件函数
            message (str): 告警消息
            severity (str): 告警严重程度
            cooldown (int): 冷却时间，单位秒
        """
        with self._lock:
            self.alert_rules[check_name] = {
                'condition': condition,
                'message': message,
                'severity': severity,
                'cooldown': cooldown
            }
            logger.info(f"添加告警规则: {check_name}")
    
    def remove_alert_rule(self, check_name: str):
        """
        移除告警规则
        
        Args:
            check_name (str): 检查名称
        """
        with self._lock:
            if check_name in self.alert_rules:
                del self.alert_rules[check_name]
                logger.info(f"移除告警规则: {check_name}")
    
    def get_alert_status(self) -> Dict[str, Any]:
        """
        获取当前告警状态
        
        Returns:
            Dict[str, Any]: 告警状态信息
        """
        with self._lock:
            current_time = time.time()
            recent_alerts = [t for t in self.alert_history if current_time - t < 3600]  # 最近1小时
            
            return {
                'recent_alerts': len(recent_alerts),
                'last_alerts': self.last_alert_status.copy(),
                'notification_channels': len(self.notification_channels)
            }

class ConsoleNotificationChannel:
    """
    控制台通知渠道
    """
    
    def send(self, alert_info: Dict[str, Any]):
        """
        发送告警通知到控制台
        
        Args:
            alert_info (Dict[str, Any]): 告警信息
        """
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert_info['timestamp']))
        severity = alert_info['severity']
        message = alert_info['message']
        check_name = alert_info['check_name']
        details = alert_info['details']
        
        if severity == 'CRITICAL':
            logger.error(f"[{timestamp}] [CRITICAL] {message} ({check_name})")
        elif severity == 'WARNING':
            logger.warning(f"[{timestamp}] [WARNING] {message} ({check_name})")
        else:
            logger.info(f"[{timestamp}] [{severity}] {message} ({check_name})")
        
        if details:
            logger.debug(f"告警详情: {details}")

# 创建全局告警管理器实例
global_alert_manager = AlertManager()

# 添加默认的控制台通知渠道
global_alert_manager.add_notification_channel(ConsoleNotificationChannel())
