import threading
import time
from PyQt5.QtCore import QObject, pyqtSignal
from commons.logger_config import get_logger
logger = get_logger(region="Event")

class EventBus(QObject):
    """事件总线，用于智能体间通信"""
    
    # 定义事件信号
    market_data_updated = pyqtSignal(dict)
    trading_signal = pyqtSignal(dict)
    order_placed = pyqtSignal(dict)
    order_updated = pyqtSignal(dict)
    risk_alert = pyqtSignal(dict)
    strategy_registered = pyqtSignal(dict)
    strategy_activated = pyqtSignal(dict)
    agent_status_changed = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.subscribers = {}
        self._lock = threading.RLock()
        # 事件发布频率控制，避免频繁日志输出
        self._event_last_published = {}
        self._log_threshold = 0.1  # 100ms内同一事件只记录一次日志
        logger.info("事件总线初始化完成")
    
    def subscribe(self, event_name, callback):
        """订阅事件
        
        Args:
            event_name (str): 事件名称
            callback (callable): 回调函数
        """
        with self._lock:
            if event_name not in self.subscribers:
                self.subscribers[event_name] = []
            self.subscribers[event_name].append(callback)
            logger.debug(f"订阅事件: {event_name}, 当前订阅数: {len(self.subscribers[event_name])}")

    def unsubscribe(self, event_name, callback):
        """取消订阅事件
        
        Args:
            event_name (str): 事件名称
            callback (callable): 回调函数
        """
        with self._lock:
            if event_name in self.subscribers:
                if callback in self.subscribers[event_name]:
                    self.subscribers[event_name].remove(callback)
                    logger.debug(f"取消订阅事件: {event_name}, 当前订阅数: {len(self.subscribers[event_name])}")

    def publish(self, event_name, data):
        """发布事件
        
        Args:
            event_name (str): 事件名称
            data (dict): 事件数据
        """
        # 控制日志输出频率，避免频繁事件产生大量日志
        current_time = time.time()
        last_time = self._event_last_published.get(event_name, 0)
        if current_time - last_time > self._log_threshold:
            logger.debug(f"发布事件: {event_name}, 数据: {data}")
            self._event_last_published[event_name] = current_time
        
        # 快速路径：如果没有订阅者，直接返回
        with self._lock:
            if event_name not in self.subscribers or not self.subscribers[event_name]:
                # 仍然发射PyQt信号，因为可能有UI组件连接
                signal = getattr(self, event_name, None)
                if signal and isinstance(signal, pyqtSignal):
                    signal.emit(data)
                return
            
            # 创建订阅者列表的副本，避免在迭代过程中修改列表
            callbacks_copy = self.subscribers[event_name].copy()
        
        # 执行回调函数
        for callback in callbacks_copy:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"执行事件回调失败: {e}")
        
        # 发射PyQt信号
        signal = getattr(self, event_name, None)
        if signal and isinstance(signal, pyqtSignal):
            signal.emit(data)

# 创建全局事件总线实例
global_event_bus = EventBus()