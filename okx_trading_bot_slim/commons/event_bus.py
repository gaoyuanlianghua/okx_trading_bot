from PyQt5.QtCore import QObject, pyqtSignal
from loguru import logger

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
        logger.info("事件总线初始化完成")
    
    def subscribe(self, event_name, callback):
        """订阅事件
        
        Args:
            event_name (str): 事件名称
            callback (callable): 回调函数
        """
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
        logger.debug(f"发布事件: {event_name}, 数据: {data}")
        
        # 调用所有订阅者的回调函数
        if event_name in self.subscribers:
            for callback in self.subscribers[event_name]:
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