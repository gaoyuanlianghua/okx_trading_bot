#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
循环事件管理器

负责主循环事件，利用监控网络延时实现 API 时间和本地时间的双轨道运行
实现定时任务和数据校准，支持秒级信号处理和分发
"""

import asyncio
import time
import logging
from datetime import datetime
import aiohttp
from concurrent.futures import ThreadPoolExecutor

# 配置日志
logging.basicConfig(
    level=logging.WARNING,  # 降低日志级别，减少性能影响
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('CycleEventManager')


class CycleEventManager:
    """
    循环事件管理器
    
    负责主循环事件，利用监控网络延时实现 API 时间和本地时间的双轨道运行
    实现定时任务和数据校准，支持秒级信号处理和分发
    """
    
    def __init__(self, api_manager=None, max_concurrent_tasks=10):
        """
        初始化循环事件管理器
        
        Args:
            api_manager: API 管理器实例，用于获取 API 时间
            max_concurrent_tasks: 最大并发任务数
        """
        self.api_manager = api_manager
        self.max_concurrent_tasks = max_concurrent_tasks
        
        # 时间相关变量
        self.local_time_offset = 0  # 本地时间与 API 时间的偏移量
        self.network_delay = 0  # 网络延时
        self.last_api_time = 0  # 最后一次获取的 API 时间
        self.last_api_time_update = 0  # 最后一次更新 API 时间的本地时间
        
        # 定时任务相关变量
        self.tasks = []  # 定时任务列表
        self.running = False  # 是否正在运行
        self.event_loop = None  # 事件循环
        self.task_semaphore = None  # 任务并发控制，将在start方法中初始化
        
        # 数据校准相关变量
        self.calibration_interval = 15  # 数据校准间隔（秒），根据网络情况动态调整
        self.last_calibration_time = 0  # 最后一次数据校准的时间
        
        # WebSocket 相关变量
        self.websocket = None
        self.websocket_url = "wss://ws.okx.com:8443/ws/v5/public"
        self.websocket_running = False
        self.websocket_task = None
        
        # 信号处理相关变量
        self.signal_queue = None  # 信号队列，将在start方法中初始化
        self.signal_handlers = {}  # 信号处理器映射
        self.signal_processor_task = None
        
        # 线程池，用于处理同步回调函数
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    def get_api_time(self):
        """
        获取 API 时间
        
        Returns:
            float: API 时间戳
        """
        if self.api_manager:
            try:
                # 调用 API 管理器获取 API 时间
                api_time = self.api_manager.get_api_time()
                if api_time:
                    # 记录 API 时间和更新时间
                    self.last_api_time = api_time
                    self.last_api_time_update = time.time()
                    
                    # 计算网络延时（假设 API 响应时间的一半）
                    current_time = time.time()
                    self.network_delay = (current_time - self.last_api_time_update) / 2
                    
                    # 计算本地时间与 API 时间的偏移量
                    self.local_time_offset = api_time - current_time
                    
                    # 根据网络延时动态调整校准间隔
                    if self.network_delay < 0.1:
                        self.calibration_interval = 30  # 网络良好，延长校准间隔
                    elif self.network_delay < 0.5:
                        self.calibration_interval = 15  # 网络一般，保持默认间隔
                    else:
                        self.calibration_interval = 5  # 网络较差，缩短校准间隔
                    
                    return api_time
            except Exception as e:
                logger.error(f"获取 API 时间失败: {e}")
        
        # 如果无法获取 API 时间，使用本地时间加上偏移量
        return time.time() + self.local_time_offset
    
    def get_local_time(self):
        """
        获取本地时间
        
        Returns:
            float: 本地时间戳
        """
        return time.time()
    
    def get_synchronized_time(self):
        """
        获取同步后的时间（优先使用 API 时间）
        
        Returns:
            float: 同步后的时间戳
        """
        # 如果 API 时间在 5 分钟内更新过，使用 API 时间
        if self.last_api_time and (time.time() - self.last_api_time_update) < 300:
            return self.last_api_time + (time.time() - self.last_api_time_update)
        # 否则使用本地时间加上偏移量
        return self.get_local_time() + self.local_time_offset
    
    def add_task(self, task_name, interval, callback, args=None, kwargs=None):
        """
        添加定时任务
        
        Args:
            task_name: 任务名称
            interval: 任务执行间隔（秒）
            callback: 任务回调函数
            args: 回调函数参数列表
            kwargs: 回调函数关键字参数
        """
        task = {
            'name': task_name,
            'interval': interval,
            'callback': callback,
            'args': args or [],
            'kwargs': kwargs or {},
            'last_executed': 0
        }
        self.tasks.append(task)
        logger.info(f"添加定时任务: {task_name}, 间隔: {interval}秒")
    
    def add_signal_handler(self, signal_type, handler):
        """
        添加信号处理器
        
        Args:
            signal_type: 信号类型
            handler: 信号处理函数
        """
        if signal_type not in self.signal_handlers:
            self.signal_handlers[signal_type] = []
        self.signal_handlers[signal_type].append(handler)
        logger.info(f"添加信号处理器: {signal_type}")
    
    async def process_signal(self, signal):
        """
        处理信号
        
        Args:
            signal: 信号对象
        """
        try:
            signal_type = signal.get('type')
            if signal_type in self.signal_handlers:
                for handler in self.signal_handlers[signal_type]:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(signal)
                    else:
                        # 使用线程池处理同步函数，避免阻塞事件循环
                        await self.event_loop.run_in_executor(
                            self.executor, handler, signal
                        )
        except Exception as e:
            logger.error(f"处理信号失败: {e}")
    
    async def signal_processor(self):
        """
        信号处理器
        """
        while self.running:
            try:
                # 非阻塞获取信号，避免队列满时阻塞
                try:
                    signal = await asyncio.wait_for(
                        self.signal_queue.get(), timeout=0.1
                    )
                    await self.process_signal(signal)
                    self.signal_queue.task_done()
                except asyncio.TimeoutError:
                    # 队列为空，继续循环
                    pass
            except Exception as e:
                logger.error(f"信号处理器异常: {e}")
                await asyncio.sleep(0.1)
    
    async def run_task(self, task):
        """
        执行定时任务
        
        Args:
            task: 任务字典
        """
        async with self.task_semaphore:
            try:
                logger.debug(f"执行定时任务: {task['name']}")
                if asyncio.iscoroutinefunction(task['callback']):
                    await task['callback'](*task['args'], **task['kwargs'])
                else:
                    # 使用线程池处理同步函数，避免阻塞事件循环
                    await self.event_loop.run_in_executor(
                        self.executor, task['callback'], *task['args'], **task['kwargs']
                    )
                task['last_executed'] = self.get_synchronized_time()
            except Exception as e:
                logger.error(f"执行定时任务 {task['name']} 失败: {e}")
    
    async def calibrate_data(self):
        """
        数据校准
        """
        try:
            logger.debug("执行数据校准...")
            
            # 更新 API 时间
            self.get_api_time()
            
            # 记录校准时间
            self.last_calibration_time = self.get_synchronized_time()
            
            logger.debug(f"数据校准完成，当前 API 时间: {self.last_api_time}, 本地时间偏移: {self.local_time_offset}, 网络延时: {self.network_delay}")
        except Exception as e:
            logger.error(f"数据校准失败: {e}")
    
    async def start_websocket(self):
        """
        启动 WebSocket 连接
        """
        self.websocket_running = True
        while self.websocket_running:
            try:
                async with aiohttp.ClientSession() as session:
                    # 兼容旧版本aiohttp，不使用ping_interval和ping_timeout参数
                    async with session.ws_connect(
                        self.websocket_url
                    ) as ws:
                        self.websocket = ws
                        logger.info("WebSocket 连接成功")
                        
                        # 订阅行情数据
                        subscribe_message = {
                            "op": "subscribe",
                            "args": [
                                {"channel": "tickers", "instId": "BTC-USDT"}
                            ]
                        }
                        await ws.send_json(subscribe_message)
                        
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                try:
                                    data = msg.json()
                                    if 'data' in data:
                                        # 将 WebSocket 数据加入信号队列
                                        # 非阻塞添加，避免队列满时阻塞
                                        try:
                                            await asyncio.wait_for(
                                                self.signal_queue.put({
                                                    'type': 'websocket_ticker',
                                                    'data': data
                                                }),
                                                timeout=0.1
                                            )
                                        except asyncio.TimeoutError:
                                            # 队列满，丢弃消息
                                            logger.warning("信号队列已满，丢弃 WebSocket 消息")
                                except Exception as e:
                                    logger.error(f"解析 WebSocket 消息失败: {e}")
                            elif msg.type == aiohttp.WSMsgType.CLOSED:
                                logger.warning("WebSocket 连接关闭")
                                break
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                logger.error("WebSocket 连接错误")
                                break
            except Exception as e:
                logger.error(f"WebSocket 异常: {e}")
                await asyncio.sleep(5)  # 5秒后重连
    
    async def main_loop(self):
        """
        主循环
        """
        # 启动信号处理器
        if hasattr(self, 'event_loop') and self.event_loop is not None:
            self.signal_processor_task = self.event_loop.create_task(self.signal_processor())
        else:
            self.signal_processor_task = asyncio.ensure_future(self.signal_processor())
        
        # 启动 WebSocket
        if hasattr(self, 'event_loop') and self.event_loop is not None:
            self.websocket_task = self.event_loop.create_task(self.start_websocket())
        else:
            self.websocket_task = asyncio.ensure_future(self.start_websocket())
        
        while self.running:
            try:
                current_time = self.get_synchronized_time()
                
                # 执行数据校准
                if current_time - self.last_calibration_time >= self.calibration_interval:
                    await self.calibrate_data()
                
                # 执行定时任务
                for task in self.tasks:
                    if current_time - task['last_executed'] >= task['interval']:
                        # 立即更新任务的 last_executed 时间戳，避免重复执行
                        task['last_executed'] = current_time
                        # 使用与旧版本 Python 兼容的方式创建异步任务
                        if hasattr(self, 'event_loop') and self.event_loop is not None:
                            self.event_loop.create_task(self.run_task(task))
                        else:
                            asyncio.ensure_future(self.run_task(task))
                
                # 短暂休眠，避免占用过多 CPU
                await asyncio.sleep(0.01)  # 提高频率到 100Hz
            except Exception as e:
                logger.error(f"主循环异常: {e}")
                await asyncio.sleep(1)
    
    def start(self, event_loop=None):
        """
        启动循环事件管理器
        
        Args:
            event_loop: 事件循环实例，如果为None则使用当前事件循环
        """
        if not self.running:
            self.running = True
            self.event_loop = event_loop or asyncio.get_event_loop()
            # 初始化信号队列和任务并发控制，使用当前事件循环
            self.signal_queue = asyncio.Queue(maxsize=1000, loop=self.event_loop)
            self.task_semaphore = asyncio.Semaphore(self.max_concurrent_tasks, loop=self.event_loop)  # 任务并发控制
            # 使用与旧版本 Python 兼容的方式创建异步任务
            self.main_loop_task = self.event_loop.create_task(self.main_loop())
            logger.info("循环事件管理器已启动")
    
    def stop(self):
        """
        停止循环事件管理器
        """
        if self.running:
            self.running = False
            self.websocket_running = False
            
            # 取消任务
            if self.signal_processor_task:
                self.signal_processor_task.cancel()
            if self.websocket_task:
                self.websocket_task.cancel()
            
            # 关闭线程池
            self.executor.shutdown(wait=False)
            
            logger.info("循环事件管理器已停止")
    
    def get_status(self):
        """
        获取循环事件管理器状态
        
        Returns:
            dict: 状态信息
        """
        return {
            'running': self.running,
            'api_time': self.last_api_time,
            'local_time_offset': self.local_time_offset,
            'network_delay': self.network_delay,
            'last_api_time_update': self.last_api_time_update,
            'last_calibration_time': self.last_calibration_time,
            'task_count': len(self.tasks),
            'websocket_running': self.websocket_running,
            'signal_handlers_count': len(self.signal_handlers),
            'signal_queue_size': self.signal_queue.qsize()
        }


if __name__ == "__main__":
    # 测试循环事件管理器
    async def test_task():
        print(f"测试任务执行: {datetime.now()}")
    
    # 创建循环事件管理器
    manager = CycleEventManager()
    
    # 添加测试任务
    manager.add_task('test_task', 1, test_task)  # 1秒间隔
    
    # 启动循环事件管理器
    manager.start()
    
    # 运行 20 秒
    asyncio.sleep(20)
    
    # 停止循环事件管理器
    manager.stop()
