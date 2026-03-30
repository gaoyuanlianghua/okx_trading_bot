"""
事件总线系统 - 提供发布-订阅模式的事件通信机制
"""

import asyncio
import json
import time
from enum import Enum, auto
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import threading
import logging

logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型枚举"""

    # 市场数据事件
    MARKET_DATA_TICKER = auto()  # 行情数据更新
    MARKET_DATA_KLINE = auto()  # K线数据更新
    MARKET_DATA_ORDERBOOK = auto()  # 订单簿数据更新
    MARKET_DATA_TRADE = auto()  # 成交数据更新

    # 订单事件
    ORDER_CREATED = auto()  # 订单创建
    ORDER_UPDATED = auto()  # 订单更新
    ORDER_CANCELLED = auto()  # 订单取消
    ORDER_FILLED = auto()  # 订单成交
    ORDER_FAILED = auto()  # 订单失败

    # 风险事件
    RISK_ALERT = auto()  # 风险警报
    RISK_LIMIT_EXCEEDED = auto()  # 风险限制超出
    RISK_POSITION_WARNING = auto()  # 仓位风险警告

    # 策略事件
    STRATEGY_SIGNAL = auto()  # 策略信号
    STRATEGY_STARTED = auto()  # 策略启动
    STRATEGY_STOPPED = auto()  # 策略停止
    STRATEGY_ERROR = auto()  # 策略错误

    # 系统事件
    SYSTEM_STARTUP = auto()  # 系统启动
    SYSTEM_SHUTDOWN = auto()  # 系统关闭
    SYSTEM_ERROR = auto()  # 系统错误
    AGENT_REGISTERED = auto()  # 智能体注册
    AGENT_UNREGISTERED = auto()  # 智能体注销

    # WebSocket事件
    WS_CONNECTED = auto()  # WebSocket连接成功
    WS_DISCONNECTED = auto()  # WebSocket断开连接
    WS_ERROR = auto()  # WebSocket错误

    # 自定义事件
    CUSTOM = auto()  # 自定义事件


@dataclass
class Event:
    """事件数据类"""

    type: EventType
    source: str  # 事件源（智能体/服务名称）
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    priority: int = 0  # 事件优先级（数值越大优先级越高）
    event_id: str = field(default_factory=lambda: f"evt_{time.time()}_{id(object())}")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "type": self.type.name,
            "source": self.source,
            "data": self.data,
            "timestamp": self.timestamp,
            "priority": self.priority,
        }

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """从字典创建事件"""
        return cls(
            type=EventType[data.get("type", "CUSTOM")],
            source=data.get("source", "unknown"),
            data=data.get("data", {}),
            timestamp=data.get("timestamp", time.time()),
            priority=data.get("priority", 0),
            event_id=data.get("event_id", f"evt_{time.time()}"),
        )


class EventBus:
    """
    事件总线 - 实现发布-订阅模式

    特性：
    1. 支持同步和异步事件处理
    2. 支持事件优先级
    3. 支持事件过滤
    4. 支持事件历史记录
    5. 线程安全
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._async_subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._event_history: List[Event] = []
        self._max_history_size = 1000
        self._lock = threading.RLock()
        self._running = False
        self._event_queue = asyncio.Queue()
        self._initialized = True

        logger.info("事件总线初始化完成")

    def subscribe(
        self, event_type: EventType, callback: Callable, async_callback: bool = False
    ):
        """
        订阅事件

        Args:
            event_type: 事件类型
            callback: 回调函数
            async_callback: 是否为异步回调
        """
        with self._lock:
            if async_callback:
                self._async_subscribers[event_type].append(callback)
            else:
                self._subscribers[event_type].append(callback)

        logger.debug(f"订阅事件: {event_type.name}, 回调: {callback.__name__}")

    def unsubscribe(self, event_type: EventType, callback: Callable):
        """
        取消订阅事件

        Args:
            event_type: 事件类型
            callback: 回调函数
        """
        with self._lock:
            if event_type in self._subscribers:
                if callback in self._subscribers[event_type]:
                    self._subscribers[event_type].remove(callback)

            if event_type in self._async_subscribers:
                if callback in self._async_subscribers[event_type]:
                    self._async_subscribers[event_type].remove(callback)

        logger.debug(f"取消订阅事件: {event_type.name}")

    def publish(self, event: Event) -> int:
        """
        发布事件（同步）

        Args:
            event: 事件对象

        Returns:
            int: 成功通知的订阅者数量
        """
        # 添加到历史记录
        self._add_to_history(event)

        notified_count = 0

        with self._lock:
            # 获取特定类型的订阅者
            callbacks = self._subscribers.get(event.type, [])

            # 获取通配符订阅者（订阅了所有事件）
            wildcard_callbacks = self._subscribers.get(EventType.CUSTOM, [])

            all_callbacks = callbacks + wildcard_callbacks

            # 按优先级排序
            # 注意：这里假设回调函数有priority属性，如果没有则使用默认值0
            # 使用try-except处理可能的类型错误
            def get_priority(cb):
                try:
                    return getattr(cb, "_priority", 0)
                except (AttributeError, TypeError):
                    return 0

            sorted_callbacks = sorted(all_callbacks, key=get_priority, reverse=True)

            for callback in sorted_callbacks:
                try:
                    callback(event)
                    notified_count += 1
                except Exception as e:
                    logger.error(f"事件处理错误 [{event.type.name}]: {e}")

        logger.debug(f"发布事件: {event.type.name}, 通知 {notified_count} 个订阅者")
        return notified_count

    async def publish_async(self, event: Event) -> int:
        """
        发布事件（异步）

        Args:
            event: 事件对象

        Returns:
            int: 成功通知的订阅者数量
        """
        # 添加到历史记录
        self._add_to_history(event)

        notified_count = 0

        with self._lock:
            # 获取异步订阅者
            async_callbacks = self._async_subscribers.get(event.type, [])
            wildcard_async_callbacks = self._async_subscribers.get(EventType.CUSTOM, [])

            all_async_callbacks = async_callbacks + wildcard_async_callbacks

            # 按优先级排序
            sorted_callbacks = sorted(
                all_async_callbacks,
                key=lambda cb: getattr(cb, "_priority", 0),
                reverse=True,
            )

            # 异步执行所有回调
            tasks = []
            for callback in sorted_callbacks:
                try:
                    task = asyncio.create_task(callback(event))
                    tasks.append(task)
                    notified_count += 1
                except Exception as e:
                    logger.error(f"异步事件处理错误 [{event.type.name}]: {e}")

            # 等待所有任务完成
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        logger.debug(f"异步发布事件: {event.type.name}, 通知 {notified_count} 个订阅者")
        return notified_count

    def _add_to_history(self, event: Event):
        """添加事件到历史记录"""
        with self._lock:
            self._event_history.append(event)

            # 限制历史记录大小
            if len(self._event_history) > self._max_history_size:
                self._event_history = self._event_history[-self._max_history_size :]

    def get_event_history(
        self, event_type: Optional[EventType] = None, limit: int = 100
    ) -> List[Event]:
        """
        获取事件历史

        Args:
            event_type: 事件类型过滤（可选）
            limit: 返回的最大事件数量

        Returns:
            List[Event]: 事件列表
        """
        with self._lock:
            if event_type:
                events = [e for e in self._event_history if e.type == event_type]
            else:
                events = self._event_history.copy()

            return events[-limit:]

    def clear_history(self):
        """清空事件历史"""
        with self._lock:
            self._event_history.clear()
        logger.info("事件历史已清空")

    def start(self):
        """启动事件总线"""
        self._running = True
        logger.info("事件总线已启动")

    def stop(self):
        """停止事件总线"""
        self._running = False
        logger.info("事件总线已停止")

    def get_stats(self) -> Dict[str, Any]:
        """获取事件总线统计信息"""
        with self._lock:
            return {
                "total_subscribers": sum(len(cb) for cb in self._subscribers.values()),
                "total_async_subscribers": sum(
                    len(cb) for cb in self._async_subscribers.values()
                ),
                "event_history_size": len(self._event_history),
                "event_types": list(self._subscribers.keys()),
                "running": self._running,
            }


# 全局事件总线实例
event_bus = EventBus()


def subscribe(event_type: EventType, priority: int = 0):
    """
    事件订阅装饰器

    用法：
        @subscribe(EventType.MARKET_DATA_TICKER, priority=1)
        def handle_ticker(event):
            print(event.data)
    """

    def decorator(func: Callable):
        func._priority = priority
        event_bus.subscribe(event_type, func)
        return func

    return decorator


def subscribe_async(event_type: EventType, priority: int = 0):
    """
    异步事件订阅装饰器

    用法：
        @subscribe_async(EventType.MARKET_DATA_TICKER, priority=1)
        async def handle_ticker_async(event):
            await process_data(event.data)
    """

    def decorator(func: Callable):
        func._priority = priority
        event_bus.subscribe(event_type, func, async_callback=True)
        return func

    return decorator
