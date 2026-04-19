"""
智能体基类 - 所有交易智能体的基础
"""

import asyncio
import time
import uuid
import logging
from enum import Enum, auto
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import threading
from concurrent.futures import ThreadPoolExecutor

from core.events.event_bus import EventBus, Event, EventType, event_bus
from core.events.agent_communication import (
    Message,
    MessageType,
    MessagePriority,
    AgentCommunicationProtocol,
    MessageTemplates,
)

# 配置日志
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """智能体状态枚举"""

    INITIALIZING = auto()  # 初始化中
    IDLE = auto()  # 空闲
    RUNNING = auto()  # 运行中
    PAUSED = auto()  # 暂停
    STOPPING = auto()  # 停止中
    STOPPED = auto()  # 已停止
    ERROR = auto()  # 错误状态
    RECOVERING = auto()  # 恢复中


@dataclass
class AgentConfig:
    """智能体配置数据类"""

    name: str
    agent_id: Optional[str] = None
    description: str = ""
    heartbeat_interval: int = 30  # 心跳间隔（秒）
    auto_recover: bool = True  # 是否自动恢复
    max_retries: int = 3  # 最大重试次数
    retry_delay: int = 5  # 重试延迟（秒）
    log_level: str = "INFO"  # 日志级别

    def __post_init__(self):
        if self.agent_id is None:
            self.agent_id = f"{self.name}_{uuid.uuid4().hex[:8]}"


@dataclass
class AgentMetrics:
    """智能体指标数据类"""

    start_time: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    message_count: int = 0
    error_count: int = 0
    task_count: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0

    def update_activity(self):
        """更新活动时间"""
        self.last_active = time.time()

    def increment_message(self):
        """增加消息计数"""
        self.message_count += 1
        self.update_activity()

    def increment_error(self):
        """增加错误计数"""
        self.error_count += 1
        self.update_activity()

    def increment_task(self):
        """增加任务计数"""
        self.task_count += 1
        self.update_activity()

    def get_uptime(self) -> float:
        """获取运行时间（秒）"""
        return time.time() - self.start_time


class BaseAgent(ABC):
    """
    智能体基类

    所有交易智能体的抽象基类，提供：
    1. 生命周期管理（初始化、启动、停止）
    2. 事件订阅和发布
    3. 消息发送和接收
    4. 心跳机制
    5. 健康检查
    6. 错误处理和恢复
    """

    def __init__(self, config: AgentConfig):
        """
        初始化智能体

        Args:
            config: 智能体配置
        """
        self.config = config
        self.agent_id = config.agent_id
        self.name = config.name
        self.status = AgentStatus.INITIALIZING
        self.metrics = AgentMetrics()

        # 事件总线
        self.event_bus = event_bus

        # 消息处理
        self._message_handlers: Dict[MessageType, List[Callable]] = {}
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._message_queue = None  # 消息队列，将在start方法中初始化
        self._message_processor_task = None  # 消息处理器任务
        self._max_concurrent_messages = 3  # 最大并发消息处理数
        self._message_semaphore = None  # 消息处理并发控制

        # 任务管理
        self._tasks: List[asyncio.Task] = []
        self._running = False
        self._stop_event = None  # 稍后在start方法中初始化

        # 事件循环
        self.loop = None

        # 线程锁
        self._lock = threading.RLock()

        # 线程池，用于处理同步回调函数
        self._executor = ThreadPoolExecutor(max_workers=3)

        # 消息处理统计
        self._message_stats = {
            'total_messages': 0,
            'processed_messages': 0,
            'failed_messages': 0,
            'queue_size': 0
        }

        # 注册到事件总线
        self._register_event_handlers()

        logger.info(f"智能体初始化完成: {self.agent_id}")

    def _register_event_handlers(self):
        """注册事件处理器"""
        # 订阅系统事件
        self.event_bus.subscribe(
            EventType.SYSTEM_SHUTDOWN, self._handle_system_shutdown
        )

        # 订阅消息事件
        self.event_bus.subscribe(EventType.CUSTOM, self._handle_incoming_message)

    def _handle_system_shutdown(self, event: Event):
        """处理系统关闭事件"""
        logger.info(f"智能体 {self.agent_id} 收到系统关闭事件")
        # 使用智能体的事件循环创建任务
        if hasattr(self, 'loop') and self.loop is not None:
            self.loop.create_task(self.stop())
        else:
            # 使用当前事件循环
            asyncio.ensure_future(self.stop())

    def _handle_incoming_message(self, event: Event):
        """处理传入消息"""
        try:
            message_data = event.data.get("message")
            if message_data:
                message = Message.from_dict(message_data)

                # 检查消息是否是发给当前智能体的
                if message.receiver == self.agent_id or message.is_broadcast():
                    # 将消息加入队列，非阻塞
                    try:
                        # 延迟处理，等待智能体启动后再处理消息
                        if hasattr(self, 'loop') and self.loop is not None and self.status == AgentStatus.RUNNING:
                            # 使用智能体的事件循环创建任务
                            self.loop.create_task(self._add_message_to_queue(message))
                        else:
                            # 智能体未启动，暂存消息
                            logger.debug(f"智能体未启动，暂存消息: {message.type.name}")
                            # 可以考虑添加到临时队列，等智能体启动后再处理
                    except Exception as e:
                        logger.error(f"添加消息到队列失败: {e}")
        except Exception as e:
            logger.error(f"处理传入消息失败: {e}")

    async def _add_message_to_queue(self, message: Message):
        """将消息添加到队列"""
        try:
            # 非阻塞添加消息，避免队列满时阻塞
            try:
                await asyncio.wait_for(
                    self._message_queue.put(message),
                    timeout=0.1
                )
                self._message_stats['total_messages'] += 1
                self._message_stats['queue_size'] = self._message_queue.qsize()
            except asyncio.TimeoutError:
                # 队列满，丢弃消息
                logger.warning(f"消息队列已满，丢弃消息: {message.type.name}")
        except Exception as e:
            logger.error(f"添加消息到队列失败: {e}")

    async def _message_processor(self):
        """消息处理器"""
        while self._running:
            try:
                # 非阻塞获取消息，避免队列空时阻塞
                try:
                    message = await asyncio.wait_for(
                        self._message_queue.get(), timeout=0.1
                    )
                    await self._process_message(message)
                    self._message_queue.task_done()
                    # 更新队列大小统计
                    self._message_stats['queue_size'] = self._message_queue.qsize()
                except asyncio.TimeoutError:
                    # 队列为空，继续循环
                    pass
            except Exception as e:
                logger.error(f"消息处理器异常: {e}")
                await asyncio.sleep(0.1)

    async def _process_message(self, message: Message):
        """
        处理消息

        Args:
            message: 消息对象
        """
        async with self._message_semaphore:
            try:
                # 验证消息
                if not AgentCommunicationProtocol.validate_message(message):
                    logger.warning(f"收到无效消息: {message.message_id}")
                    return

                # 更新指标
                self.metrics.increment_message()

                # 处理特定消息类型
                handlers = self._message_handlers.get(message.type, [])
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(message)
                        else:
                            # 使用线程池处理同步函数，避免阻塞事件循环
                            if hasattr(self, 'loop') and self.loop is not None:
                                await self.loop.run_in_executor(
                                    self._executor, handler, message
                                )
                            else:
                                # 使用当前事件循环
                                loop = asyncio.get_event_loop()
                                await loop.run_in_executor(
                                    self._executor, handler, message
                                )
                    except Exception as e:
                        logger.error(f"消息处理错误: {e}")
                        self.metrics.increment_error()
                        self._message_stats['failed_messages'] += 1

                # 处理通用命令
                await self._handle_command(message)
                self._message_stats['processed_messages'] += 1
            except Exception as e:
                logger.error(f"处理消息失败: {e}")
                self._message_stats['failed_messages'] += 1

    async def _handle_command(self, message: Message):
        """
        处理命令消息

        Args:
            message: 消息对象
        """
        if message.type == MessageType.COMMAND_START:
            await self.start()
        elif message.type == MessageType.COMMAND_STOP:
            await self.stop()
        elif message.type == MessageType.COMMAND_PAUSE:
            await self.pause()
        elif message.type == MessageType.COMMAND_RESUME:
            await self.resume()
        elif message.type == MessageType.REQUEST_STATUS:
            await self._send_status_response(message)
        elif message.type == MessageType.HEARTBEAT:
            await self._send_heartbeat_response(message)

    async def _send_status_response(self, request_message: Message):
        """发送状态响应"""
        response = MessageTemplates.status_response(
            sender=self.agent_id,
            receiver=request_message.sender,
            request_message=request_message,
            status=self.status.name,
            details=self.get_status(),
        )
        await self.send_message(response)

    async def _send_heartbeat_response(self, request_message: Message):
        """发送心跳响应"""
        response = Message.create_response(
            sender=self.agent_id,
            receiver=request_message.sender,
            request_message=request_message,
            payload={"status": "alive", "timestamp": time.time()},
        )
        await self.send_message(response)

    def register_message_handler(self, message_type: MessageType, handler: Callable):
        """
        注册消息处理器

        Args:
            message_type: 消息类型
            handler: 处理函数
        """
        if message_type not in self._message_handlers:
            self._message_handlers[message_type] = []
        self._message_handlers[message_type].append(handler)
        logger.debug(f"注册消息处理器: {message_type.name}")

    async def send_message(self, message: Message) -> bool:
        """
        发送消息

        Args:
            message: 消息对象

        Returns:
            bool: 是否发送成功
        """
        try:
            # 发布消息事件
            event = Event(
                type=EventType.CUSTOM,
                source=self.agent_id,
                data={"message": message.to_dict()},
                priority=message.priority.value,
            )

            await self.event_bus.publish_async(event)
            return True
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False

    async def send_request(
        self,
        receiver: str,
        request_type: MessageType,
        payload: Dict[str, Any] = None,
        timeout: int = 30,
    ) -> Optional[Message]:
        """
        发送请求并等待响应

        Args:
            receiver: 接收者ID
            request_type: 请求类型
            payload: 请求数据
            timeout: 超时时间（秒）

        Returns:
            Optional[Message]: 响应消息，超时返回None
        """
        # 创建请求消息
        request = Message.create_request(
            sender=self.agent_id,
            receiver=receiver,
            request_type=request_type,
            payload=payload or {},
        )

        # 创建Future等待响应
        future = asyncio.Future()
        self._pending_responses[request.message_id] = future

        # 发送请求
        await self.send_message(request)

        try:
            # 等待响应
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.warning(f"请求超时: {request.message_id}")
            return None
        finally:
            self._pending_responses.pop(request.message_id, None)

    async def handle_response(self, response: Message):
        """
        处理响应消息

        Args:
            response: 响应消息
        """
        if (
            response.correlation_id
            and response.correlation_id in self._pending_responses
        ):
            future = self._pending_responses[response.correlation_id]
            if not future.done():
                future.set_result(response)

    async def start(self) -> bool:
        """
        启动智能体

        Returns:
            bool: 是否启动成功
        """
        if self.status == AgentStatus.RUNNING:
            logger.warning(f"智能体 {self.agent_id} 已经在运行中")
            return True

        try:
            self.status = AgentStatus.INITIALIZING
            self._running = True
            
            # 获取当前事件循环
            self.loop = asyncio.get_event_loop()
            
            # 初始化停止事件，确保使用当前事件循环
            if self._stop_event is None:
                self._stop_event = asyncio.Event()
            else:
                # 清除事件状态
                self._stop_event.clear()

            # 初始化消息队列，使用当前事件循环
            if self._message_queue is None:
                self._message_queue = asyncio.Queue(maxsize=1000, loop=self.loop)
            # 初始化消息处理并发控制
            self._message_semaphore = asyncio.Semaphore(self._max_concurrent_messages, loop=self.loop)

            # 执行子类初始化
            await self._initialize()

            # 启动主循环
            main_task = self.loop.create_task(self._main_loop())
            self._tasks.append(main_task)

            # 启动心跳任务
            heartbeat_task = self.loop.create_task(self._heartbeat_loop())
            self._tasks.append(heartbeat_task)

            # 启动消息处理器任务
            self._message_processor_task = self.loop.create_task(self._message_processor())
            self._tasks.append(self._message_processor_task)

            self.status = AgentStatus.RUNNING
            self.metrics.start_time = time.time()

            # 发布启动事件
            event = Event(
                type=EventType.AGENT_REGISTERED,
                source=self.agent_id,
                data={"agent_id": self.agent_id, "name": self.name},
            )
            await self.event_bus.publish_async(event)

            logger.info(f"智能体启动成功: {self.agent_id}")
            return True

        except Exception as e:
            self.status = AgentStatus.ERROR
            logger.error(f"智能体启动失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def stop(self) -> bool:
        """
        停止智能体

        Returns:
            bool: 是否停止成功
        """
        import traceback
        logger.warning(f"智能体 {self.agent_id} 的stop()方法被调用！调用堆栈:\n{traceback.format_stack()}")
        
        if self.status == AgentStatus.STOPPED:
            return True

        try:
            self.status = AgentStatus.STOPPING
            self._running = False
            if self._stop_event:
                self._stop_event.set()

            # 执行子类清理
            await self._cleanup()

            # 取消所有任务
            for task in self._tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            self._tasks.clear()
            
            # 关闭线程池
            self._executor.shutdown(wait=False)
            
            self.status = AgentStatus.STOPPED

            # 发布停止事件
            event = Event(
                type=EventType.AGENT_UNREGISTERED,
                source=self.agent_id,
                data={"agent_id": self.agent_id, "name": self.name},
            )
            await self.event_bus.publish_async(event)

            logger.info(f"智能体停止成功: {self.agent_id}")
            return True

        except Exception as e:
            self.status = AgentStatus.ERROR
            logger.error(f"智能体停止失败: {e}")
            return False

    async def pause(self) -> bool:
        """
        暂停智能体

        Returns:
            bool: 是否暂停成功
        """
        if self.status != AgentStatus.RUNNING:
            logger.warning(f"智能体 {self.agent_id} 不在运行状态，无法暂停")
            return False

        self.status = AgentStatus.PAUSED
        logger.info(f"智能体已暂停: {self.agent_id}")
        return True

    async def resume(self) -> bool:
        """
        恢复智能体

        Returns:
            bool: 是否恢复成功
        """
        if self.status != AgentStatus.PAUSED:
            logger.warning(f"智能体 {self.agent_id} 不在暂停状态，无法恢复")
            return False

        self.status = AgentStatus.RUNNING
        logger.info(f"智能体已恢复: {self.agent_id}")
        return True

    async def _main_loop(self):
        """主循环 - 子类应重写此方法"""
        import traceback
        while self._running:
            try:
                if self.status == AgentStatus.RUNNING:
                    await self._execute_cycle()

                # 等待停止事件或超时
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass

            except Exception as e:
                error_detail = traceback.format_exc()
                logger.error(f"主循环错误: {e}")
                logger.error(f"详细错误信息:\n{error_detail}")
                self.metrics.increment_error()

                if self.config.auto_recover:
                    await self._recover()

    async def _heartbeat_loop(self):
        """心跳循环"""
        while self._running:
            try:
                # 发送心跳广播
                heartbeat = Message.create_heartbeat(self.agent_id)
                await self.send_message(heartbeat)

                # 等待下一个心跳周期
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.config.heartbeat_interval
                )
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                logger.error(f"心跳错误: {e}")
                import traceback
                traceback.print_exc()

    async def _recover(self):
        """错误恢复"""
        self.status = AgentStatus.RECOVERING
        logger.info(f"智能体恢复中: {self.agent_id}")

        for attempt in range(self.config.max_retries):
            try:
                await asyncio.sleep(self.config.retry_delay)
                await self._initialize()
                self.status = AgentStatus.RUNNING
                logger.info(f"智能体恢复成功: {self.agent_id}")
                return
            except Exception as e:
                logger.error(f"恢复尝试 {attempt + 1} 失败: {e}")

        self.status = AgentStatus.ERROR
        logger.error(f"智能体恢复失败: {self.agent_id}")

    def get_status(self) -> Dict[str, Any]:
        """
        获取智能体状态

        Returns:
            Dict[str, Any]: 状态信息
        """
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "status": self.status.name,
            "uptime": self.metrics.get_uptime(),
            "metrics": {
                "message_count": self.metrics.message_count,
                "error_count": self.metrics.error_count,
                "task_count": self.metrics.task_count,
                "last_active": self.metrics.last_active,
            },
            "message_stats": {
                "total_messages": self._message_stats['total_messages'],
                "processed_messages": self._message_stats['processed_messages'],
                "failed_messages": self._message_stats['failed_messages'],
                "queue_size": self._message_stats['queue_size'],
            },
        }

    def is_healthy(self) -> bool:
        """
        健康检查

        Returns:
            bool: 是否健康
        """
        # 检查状态
        if self.status not in [AgentStatus.RUNNING, AgentStatus.IDLE]:
            return False

        # 检查是否活跃
        inactive_time = time.time() - self.metrics.last_active
        if inactive_time > self.config.heartbeat_interval * 3:
            return False

        # 检查错误率
        if self.metrics.message_count > 0:
            error_rate = self.metrics.error_count / self.metrics.message_count
            if error_rate > 0.1:  # 错误率超过10%
                return False

        return True

    @abstractmethod
    async def _initialize(self):
        """初始化 - 子类必须实现"""
        pass

    @abstractmethod
    async def _cleanup(self):
        """清理 - 子类必须实现"""
        pass

    @abstractmethod
    async def _execute_cycle(self):
        """执行周期 - 子类必须实现"""
        pass
