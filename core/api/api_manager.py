#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API管理器
负责管理所有的API调用，处理API返回的信息
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, List, Callable
from concurrent.futures import ThreadPoolExecutor
from core.api.okx_rest_client import OKXRESTClient
from core.api.api_response_parser import APIResponseParser

# 配置日志
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('APIManager')


class APIManager:
    """API管理器"""
    
    def __init__(self, api_key: str, api_secret: str, passphrase: str, is_test: bool = False, max_concurrent_messages: int = 5):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.is_test = is_test
        self.rest_client = None
        self.parser = APIResponseParser()
        self._initialize_client()
        
        # 事件循环
        self.loop = None
        
        # 消息分发相关
        self.message_handlers = {}  # 消息处理器映射，格式: {agent_type: {message_type: [handlers]}}
        self.message_queue = None  # 消息队列，将在start方法中初始化
        self.running = False  # 消息处理器运行状态
        self.message_processor_task = None  # 消息处理器任务
        self.max_concurrent_messages = max_concurrent_messages  # 最大并发消息处理数
        self.message_semaphore = None  # 消息处理并发控制，将在start方法中初始化
        
        # 线程池，用于处理同步回调函数
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        # 消息处理统计
        self.message_stats = {
            'total_messages': 0,
            'processed_messages': 0,
            'failed_messages': 0,
            'queue_size': 0
        }
    
    def _initialize_client(self):
        """初始化API客户端"""
        try:
            self.rest_client = OKXRESTClient(
                api_key=self.api_key,
                api_secret=self.api_secret,
                passphrase=self.passphrase,
                is_test=self.is_test
            )
            logger.info("API客户端初始化成功")
        except Exception as e:
            logger.error(f"API客户端初始化失败: {e}")
            self.rest_client = None
    
    async def get_account_balance(self) -> Dict[str, Any]:
        """获取账户余额"""
        try:
            if not self.rest_client:
                self._initialize_client()
                if not self.rest_client:
                    return {}
            
            response = await self.rest_client.get_account_balance()
            if response:
                balance_data = self.parser.parse_balance_response(response)
                # 分发消息给智能体
                await self.distribute_message('balance', balance_data)
                return balance_data
            return {}
        except Exception as e:
            logger.error(f"获取账户余额失败: {e}")
            return {}
    
    async def get_positions(self) -> Dict[str, Any]:
        """获取持仓信息"""
        try:
            if not self.rest_client:
                self._initialize_client()
                if not self.rest_client:
                    return {}
            
            response = await self.rest_client.get_positions()
            if response:
                positions_data = self.parser.parse_positions_response(response)
                # 分发消息给智能体
                await self.distribute_message('positions', positions_data)
                return positions_data
            return {}
        except Exception as e:
            logger.error(f"获取持仓信息失败: {e}")
            return {}
    
    async def get_ticker(self, instrument_id: str) -> Dict[str, Any]:
        """获取行情数据"""
        try:
            if not self.rest_client:
                self._initialize_client()
                if not self.rest_client:
                    return {}
            
            response = await self.rest_client.get_ticker(instrument_id)
            if response:
                # 构建完整的响应体格式
                full_response = {
                    'data': [response],
                    'ts': response.get('ts')
                }
                ticker_data = self.parser.parse_ticker_response(full_response)
                # 分发消息给智能体
                await self.distribute_message('ticker', ticker_data)
                return ticker_data
            return {}
        except Exception as e:
            logger.error(f"获取行情数据失败: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    async def get_orders_pending(self) -> Dict[str, Any]:
        """获取未成交订单"""
        try:
            if not self.rest_client:
                self._initialize_client()
                if not self.rest_client:
                    return {}
            
            response = await self.rest_client.get_orders_pending()
            if response:
                orders_data = self.parser.parse_order_response(response)
                # 分发消息给智能体
                await self.distribute_message('orders', orders_data)
                return orders_data
            return {}
        except Exception as e:
            logger.error(f"获取未成交订单失败: {e}")
            return {}
    
    async def place_order(self, **kwargs) -> Optional[str]:
        """放置订单"""
        try:
            if not self.rest_client:
                self._initialize_client()
                if not self.rest_client:
                    return None
            
            order_id = await self.rest_client.place_order(**kwargs)
            # 分发消息给智能体
            await self.distribute_message('order_placed', {
                'order_id': order_id,
                'params': kwargs
            })
            return order_id
        except Exception as e:
            logger.error(f"放置订单失败: {e}")
            # 分发错误消息给智能体
            await self.distribute_message('order_error', {
                'error': str(e),
                'params': kwargs
            })
            return None
    
    async def cancel_order(self, inst_id: str, ord_id: str) -> bool:
        """撤销订单"""
        try:
            if not self.rest_client:
                self._initialize_client()
                if not self.rest_client:
                    return False
            
            success = await self.rest_client.cancel_order(inst_id, ord_id)
            # 分发消息给智能体
            await self.distribute_message('order_cancelled', {
                'inst_id': inst_id,
                'ord_id': ord_id,
                'success': success
            })
            return success
        except Exception as e:
            logger.error(f"撤销订单失败: {e}")
            # 分发错误消息给智能体
            await self.distribute_message('order_error', {
                'error': str(e),
                'inst_id': inst_id,
                'ord_id': ord_id
            })
            return False
    
    def get_parser(self) -> APIResponseParser:
        """获取API响应解析器"""
        return self.parser
    
    def get_api_timestamp(self) -> Optional[float]:
        """获取API时间戳"""
        # 尝试从解析器中获取最新的时间戳
        balance_timestamp = self.parser.get_timestamp('balance')
        positions_timestamp = self.parser.get_timestamp('positions')
        ticker_timestamp = self.parser.get_timestamp('ticker')
        orders_timestamp = self.parser.get_timestamp('orders')
        
        timestamps = [t for t in [balance_timestamp, positions_timestamp, ticker_timestamp, orders_timestamp] if t]
        if timestamps:
            return max(timestamps)
        return None
    
    def get_api_time(self) -> float:
        """获取 API 时间
        
        Returns:
            float: API 时间戳
        """
        try:
            if not self.rest_client:
                self._initialize_client()
                if not self.rest_client:
                    return 0
            
            # 调用 OKX REST 客户端获取 API 时间
            # 注意：这里需要确保 OKXRESTClient 有同步的 get_api_time 方法
            return self.rest_client.get_api_time()
        except Exception as e:
            logger.error(f"获取 API 时间失败: {e}")
            return 0
    
    def register_message_handler(self, agent_type: str, message_type: str, handler: Callable):
        """注册消息处理器
        
        Args:
            agent_type: 智能体类型
            message_type: 消息类型
            handler: 消息处理函数
        """
        if agent_type not in self.message_handlers:
            self.message_handlers[agent_type] = {}
        if message_type not in self.message_handlers[agent_type]:
            self.message_handlers[agent_type][message_type] = []
        self.message_handlers[agent_type][message_type].append(handler)
        logger.info(f"为智能体类型 {agent_type} 注册消息处理器: {message_type}")
    
    async def add_message(self, message_type: str, message: Dict[str, Any], agent_type: str = None):
        """添加消息到队列
        
        Args:
            message_type: 消息类型
            message: 消息内容
            agent_type: 智能体类型，如果为 None，则分发消息给所有智能体
        """
        # 非阻塞添加消息，避免队列满时阻塞
        try:
            await asyncio.wait_for(
                self.message_queue.put({
                    'type': message_type,
                    'message': message,
                    'agent_type': agent_type,
                    'timestamp': time.time()
                }),
                timeout=0.1
            )
            self.message_stats['total_messages'] += 1
            self.message_stats['queue_size'] = self.message_queue.qsize()
        except asyncio.TimeoutError:
            # 队列满，丢弃消息
            logger.warning(f"消息队列已满，丢弃消息: {message_type}")
    
    async def process_message(self, message):
        """处理消息
        
        Args:
            message: 消息对象
        """
        async with self.message_semaphore:
            try:
                message_type = message.get('type')
                message_content = message.get('message')
                agent_type = message.get('agent_type')
                
                # 根据智能体类型分发消息
                if agent_type:
                    # 只分发消息给指定的智能体
                    if agent_type in self.message_handlers:
                        handlers_by_type = self.message_handlers[agent_type]
                        if message_type in handlers_by_type:
                            for handler in handlers_by_type[message_type]:
                                if asyncio.iscoroutinefunction(handler):
                                    await handler(message_content)
                                else:
                                    # 使用线程池处理同步函数，避免阻塞事件循环
                                    if self.loop is not None:
                                        await self.loop.run_in_executor(
                                            self.executor, handler, message_content
                                        )
                                    else:
                                        # 使用当前事件循环
                                        await asyncio.get_event_loop().run_in_executor(
                                            self.executor, handler, message_content
                                        )
                else:
                    # 分发消息给所有智能体
                    for agent_type, handlers_by_type in self.message_handlers.items():
                        if message_type in handlers_by_type:
                            for handler in handlers_by_type[message_type]:
                                if asyncio.iscoroutinefunction(handler):
                                    await handler(message_content)
                                else:
                                    # 使用线程池处理同步函数，避免阻塞事件循环
                                    if self.loop is not None:
                                        await self.loop.run_in_executor(
                                            self.executor, handler, message_content
                                        )
                                    else:
                                        # 使用当前事件循环
                                        await asyncio.get_event_loop().run_in_executor(
                                            self.executor, handler, message_content
                                        )
                self.message_stats['processed_messages'] += 1
            except Exception as e:
                logger.error(f"处理消息失败: {e}")
                self.message_stats['failed_messages'] += 1
    
    async def message_processor(self):
        """消息处理器主循环"""
        while self.running:
            try:
                # 非阻塞获取消息，避免队列空时阻塞
                try:
                    message = await asyncio.wait_for(
                        self.message_queue.get(), timeout=0.1
                    )
                    await self.process_message(message)
                    self.message_queue.task_done()
                    # 更新队列大小统计
                    self.message_stats['queue_size'] = self.message_queue.qsize()
                except asyncio.TimeoutError:
                    # 队列为空，继续循环
                    pass
            except Exception as e:
                logger.error(f"消息处理器异常: {e}")
                await asyncio.sleep(0.1)
    
    def start_message_processor(self):
        """启动消息处理器"""
        if not self.running:
            self.running = True
            # 获取当前事件循环
            self.loop = asyncio.get_event_loop()
            # 初始化消息队列，使用当前事件循环
            if self.message_queue is None:
                self.message_queue = asyncio.Queue(maxsize=1000, loop=self.loop)
            # 初始化消息处理并发控制，使用当前事件循环
            if self.message_semaphore is None:
                self.message_semaphore = asyncio.Semaphore(self.max_concurrent_messages, loop=self.loop)
            # 使用当前事件循环启动消息处理器
            self.message_processor_task = self.loop.create_task(self.message_processor())
            logger.info("消息处理器已启动")
    
    def stop_message_processor(self):
        """停止消息处理器"""
        if self.running:
            self.running = False
            if self.message_processor_task:
                self.message_processor_task.cancel()
            # 关闭线程池
            self.executor.shutdown(wait=False)
            logger.info("消息处理器已停止")
    
    async def distribute_message(self, message_type: str, message: Dict[str, Any], agent_type: str = None):
        """分发消息给注册的处理器
        
        Args:
            message_type: 消息类型
            message: 消息内容
            agent_type: 智能体类型，如果为 None，则分发消息给所有智能体
        """
        # 如果消息处理器未启动，启动它
        if not self.running:
            self.start_message_processor()
        
        # 添加消息到队列
        await self.add_message(message_type, message, agent_type)
    
    def get_message_stats(self) -> Dict[str, int]:
        """获取消息处理统计信息
        
        Returns:
            Dict[str, int]: 消息处理统计信息
        """
        return self.message_stats
