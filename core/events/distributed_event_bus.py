"""
分布式事件总线 - 支持跨节点的事件通信
"""

import asyncio
import json
import time
from enum import Enum, auto
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import threading
import redis
import logging

from core.events.event_bus import EventType, Event

logger = logging.getLogger(__name__)


class DistributedEventBus:
    """
    分布式事件总线 - 支持跨节点的事件通信
    
    使用Redis作为消息队列，实现跨节点的事件发布和订阅
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
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        初始化分布式事件总线
        
        Args:
            redis_url: Redis连接URL
        """
        if self._initialized:
            return
        
        # 本地订阅者
        self._subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._async_subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        
        # 本地事件历史
        self._event_history: List[Event] = []
        self._max_history_size = 1000
        
        # 线程安全锁
        self._lock = threading.RLock()
        
        # 运行状态
        self._running = False
        
        # Redis连接
        self._redis_url = redis_url
        self._redis = None
        self._pubsub = None
        
        # 初始化Redis连接
        self._init_redis()
        
        # 启动订阅线程
        self._subscribe_thread = None
        
        self._initialized = True
        
        logger.info("分布式事件总线初始化完成")
    
    def _init_redis(self):
        """
        初始化Redis连接
        """
        try:
            self._redis = redis.from_url(self._redis_url, decode_responses=True)
            self._pubsub = self._redis.pubsub()
            logger.info("Redis连接成功")
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            self._redis = None
            self._pubsub = None
    
    def start(self):
        """
        启动分布式事件总线
        """
        self._running = True
        
        # 启动Redis订阅线程
        if self._pubsub:
            # 订阅所有事件频道
            self._pubsub.subscribe("events")
            self._subscribe_thread = threading.Thread(target=self._listen_for_events, daemon=True)
            self._subscribe_thread.start()
        
        logger.info("分布式事件总线已启动")
    
    def stop(self):
        """
        停止分布式事件总线
        """
        self._running = False
        
        # 停止Redis订阅
        if self._pubsub:
            self._pubsub.unsubscribe()
        
        # 等待订阅线程结束
        if self._subscribe_thread and self._subscribe_thread.is_alive():
            self._subscribe_thread.join(timeout=2.0)
        
        # 关闭Redis连接
        if self._redis:
            self._redis.close()
        
        logger.info("分布式事件总线已停止")
    
    def _listen_for_events(self):
        """
        监听Redis中的事件
        """
        if not self._pubsub:
            return
        
        try:
            for message in self._pubsub.listen():
                if not self._running:
                    break
                
                if message['type'] == 'message':
                    try:
                        # 解析事件
                        event_data = json.loads(message['data'])
                        event = Event.from_dict(event_data)
                        
                        # 处理本地订阅者
                        self._process_local_subscribers(event)
                        
                        # 添加到本地历史
                        self._add_to_history(event)
                    except Exception as e:
                        logger.error(f"处理Redis事件失败: {e}")
        except Exception as e:
            logger.error(f"监听Redis事件失败: {e}")
    
    def _process_local_subscribers(self, event: Event):
        """
        处理本地订阅者
        
        Args:
            event: 事件对象
        """
        notified_count = 0
        
        with self._lock:
            # 处理同步订阅者
            callbacks = self._subscribers.get(event.type, [])
            wildcard_callbacks = self._subscribers.get(EventType.CUSTOM, [])
            all_callbacks = callbacks + wildcard_callbacks
            
            # 按优先级排序
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
            
            # 处理异步订阅者
            async_callbacks = self._async_subscribers.get(event.type, [])
            wildcard_async_callbacks = self._async_subscribers.get(EventType.CUSTOM, [])
            all_async_callbacks = async_callbacks + wildcard_async_callbacks
            
            if all_async_callbacks:
                # 创建异步任务
                async def process_async_callbacks():
                    tasks = []
                    for callback in all_async_callbacks:
                        try:
                            task = asyncio.create_task(callback(event))
                            tasks.append(task)
                        except Exception as e:
                            logger.error(f"异步事件处理错误 [{event.type.name}]: {e}")
                    
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
                
                # 运行异步任务
                loop = asyncio.new_event_loop()
                loop.run_until_complete(process_async_callbacks())
                loop.close()
        
        logger.debug(f"处理本地订阅者: {event.type.name}, 通知 {notified_count} 个订阅者")
    
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
        # 添加到本地历史
        self._add_to_history(event)
        
        # 处理本地订阅者
        self._process_local_subscribers(event)
        
        # 发布到Redis
        if self._redis:
            try:
                event_json = event.to_json()
                self._redis.publish("events", event_json)
                logger.debug(f"发布事件到Redis: {event.type.name}")
            except Exception as e:
                logger.error(f"发布事件到Redis失败: {e}")
        
        return 0  # 无法准确统计分布式订阅者数量
    
    async def publish_async(self, event: Event) -> int:
        """
        发布事件（异步）
        
        Args:
            event: 事件对象
            
        Returns:
            int: 成功通知的订阅者数量
        """
        # 添加到本地历史
        self._add_to_history(event)
        
        # 处理本地订阅者
        self._process_local_subscribers(event)
        
        # 发布到Redis
        if self._redis:
            try:
                event_json = event.to_json()
                self._redis.publish("events", event_json)
                logger.debug(f"异步发布事件到Redis: {event.type.name}")
            except Exception as e:
                logger.error(f"异步发布事件到Redis失败: {e}")
        
        return 0  # 无法准确统计分布式订阅者数量
    
    def _add_to_history(self, event: Event):
        """
        添加事件到历史记录
        
        Args:
            event: 事件对象
        """
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
        """
        清空事件历史
        """
        with self._lock:
            self._event_history.clear()
        logger.info("事件历史已清空")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取事件总线统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        with self._lock:
            return {
                "total_subscribers": sum(len(cb) for cb in self._subscribers.values()),
                "total_async_subscribers": sum(
                    len(cb) for cb in self._async_subscribers.values()
                ),
                "event_history_size": len(self._event_history),
                "event_types": list(self._subscribers.keys()),
                "running": self._running,
                "redis_connected": self._redis is not None,
            }


# 全局分布式事件总线实例
distributed_event_bus = DistributedEventBus()