"""
市场数据智能体 - 负责获取和管理市场数据
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_agent import BaseAgent, AgentConfig, AgentStatus
from core.events.event_bus import Event, EventType
from core.events.agent_communication import Message, MessageType, MessageTemplates
from core.api.exchange_manager import exchange_manager
from core.utils.logger import get_logger

logger = get_logger(__name__)


class MarketDataAgent(BaseAgent):
    """
    市场数据智能体

    职责：
    1. 获取实时行情数据（ticker、orderbook、kline等）
    2. 管理WebSocket订阅
    3. 缓存市场数据
    4. 提供数据查询接口
    """

    def __init__(
        self,
        config: AgentConfig,
        exchange_name: str = "okx",
        **exchange_kwargs
    ):
        """
        初始化市场数据智能体

        Args:
            config: 智能体配置
            exchange_name: 交易所名称
            **exchange_kwargs: 交易所客户端初始化参数
        """
        super().__init__(config)

        # 交易所配置
        self.exchange_name = exchange_name
        
        # API客户端
        self.rest_client = exchange_manager.get_exchange(exchange_name, **exchange_kwargs)
        self.ws_client = exchange_manager.get_websocket_client(exchange_name, **exchange_kwargs)
        
        # 确保客户端初始化成功
        if not self.rest_client:
            logger.warning(f"无法创建{exchange_name} REST客户端，部分功能可能不可用")
        if not self.ws_client:
            logger.warning(f"无法创建{exchange_name} WebSocket客户端，部分功能可能不可用")

        # 数据缓存
        self._ticker_cache: Dict[str, Dict] = {}
        self._orderbook_cache: Dict[str, Dict] = {}
        self._kline_cache: Dict[str, List] = {}
        self._trade_cache: Dict[str, List] = {}

        # 缓存元数据 - 用于跟踪最后访问时间
        self._cache_metadata: Dict[str, Dict] = {}

        # 订阅管理
        self._subscribed_inst_ids: set = set()
        self._default_inst_id = "BTC-USDT-SWAP"

        # 数据更新计数
        self._update_count = 0

        # 内存优化配置
        self._max_cache_size = 1000  # 最大缓存大小
        self._cache_cleanup_interval = 300  # 缓存清理间隔（秒）
        self._last_cleanup_time = 0  # 上次清理时间

        logger.info(f"市场数据智能体初始化完成: {self.agent_id}")

    async def _initialize(self):
        """初始化"""
        # 注册消息处理器
        self.register_message_handler(
            MessageType.REQUEST_DATA, self._handle_data_request
        )

        # 订阅市场数据事件 - 使用lambda包装以避免bound method问题
        self.event_bus.subscribe(
            EventType.MARKET_DATA_TICKER, self._on_ticker_update, async_callback=True
        )
        self.event_bus.subscribe(
            EventType.MARKET_DATA_ORDERBOOK,
            self._on_orderbook_update,
            async_callback=True,
        )
        self.event_bus.subscribe(
            EventType.MARKET_DATA_KLINE, self._on_kline_update, async_callback=True
        )
        self.event_bus.subscribe(
            EventType.MARKET_DATA_TRADE, self._on_trade_update, async_callback=True
        )

        logger.info("市场数据智能体初始化完成")

    async def _cleanup(self):
        """清理"""
        # 取消所有订阅
        if self.ws_client:
            for inst_id in list(self._subscribed_inst_ids):
                await self.ws_client.unsubscribe("tickers", inst_id)
                await self.ws_client.unsubscribe("books", inst_id)

        # 清空缓存
        self._ticker_cache.clear()
        self._orderbook_cache.clear()
        self._kline_cache.clear()
        self._trade_cache.clear()

        logger.info("市场数据智能体已清理")

    async def _execute_cycle(self):
        """执行周期"""
        # 确保WebSocket连接并订阅默认产品
        if self.ws_client and not self.ws_client.is_connected():
            await self.ws_client.connect_public()

        # 订阅默认产品
        if self._default_inst_id not in self._subscribed_inst_ids:
            await self.subscribe_instrument(self._default_inst_id)

        # 定期更新REST数据作为备份
        await self._update_rest_data()

        # 定期清理缓存
        await self._cleanup_cache()

        # 等待一段时间
        await asyncio.sleep(5)

    async def _cleanup_cache(self):
        """清理缓存，移除长时间未使用的数据"""
        import time

        current_time = time.time()

        # 检查是否需要清理
        if current_time - self._last_cleanup_time < self._cache_cleanup_interval:
            return

        self._last_cleanup_time = current_time

        # 清理长时间未使用的缓存
        expired_keys = []
        cleanup_threshold = current_time - 3600  # 1小时未使用的缓存

        for key, metadata in self._cache_metadata.items():
            if metadata.get("last_access_time", 0) < cleanup_threshold:
                expired_keys.append(key)

        for key in expired_keys:
            # 从各个缓存中移除
            if key in self._ticker_cache:
                del self._ticker_cache[key]
            if key in self._orderbook_cache:
                del self._orderbook_cache[key]
            if key in self._kline_cache:
                del self._kline_cache[key]
            if key in self._trade_cache:
                del self._trade_cache[key]
            if key in self._cache_metadata:
                del self._cache_metadata[key]

        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期缓存项")

    async def _update_rest_data(self):
        """通过REST API更新数据"""
        if not self.rest_client:
            return

        for inst_id in list(self._subscribed_inst_ids):
            try:
                # 获取ticker
                ticker = await self.rest_client.get_ticker(inst_id)
                if ticker:
                    self._ticker_cache[inst_id] = ticker

                # 获取orderbook
                orderbook = await self.rest_client.get_orderbook(inst_id)
                if orderbook:
                    self._orderbook_cache[inst_id] = orderbook

            except Exception as e:
                logger.error(f"更新REST数据失败 {inst_id}: {e}")

    async def _handle_data_request(self, message: Message):
        """处理数据请求"""
        payload = message.payload
        data_type = payload.get("data_type")
        inst_id = payload.get("inst_id", self._default_inst_id)

        response_data = {}

        if data_type == "ticker":
            response_data = self.get_ticker(inst_id)
        elif data_type == "orderbook":
            response_data = self.get_orderbook(inst_id)
        elif data_type == "kline":
            bar = payload.get("bar", "1m")
            response_data = self.get_kline(inst_id, bar)
        elif data_type == "trades":
            response_data = self.get_trades(inst_id)

        # 发送响应
        response = Message.create_response(
            sender=self.agent_id,
            receiver=message.sender,
            request_message=message,
            payload={"data": response_data},
        )
        await self.send_message(response)

    async def _on_ticker_update(self, event: Event):
        """处理ticker更新"""
        data = event.data.get("data", [])
        inst_id = event.data.get("inst_id", "")

        if data and inst_id:
            self._ticker_cache[inst_id] = data[0]
            self._update_count += 1
            self.metrics.update_activity()

            # 更新缓存元数据
            self._update_cache_metadata(inst_id)

            # 发布市场数据更新事件
            await self.event_bus.publish_async(
                Event(
                    type=EventType.MARKET_DATA_TICKER,
                    source="market_data_agent",
                    data={
                        "channel": "tickers",
                        "inst_id": inst_id,
                        "data": data
                    }
                )
            )

            logger.debug(f"Ticker更新: {inst_id}, 价格: {data[0].get('last')}")

    async def _on_orderbook_update(self, event: Event):
        """处理orderbook更新"""
        data = event.data.get("data", [])
        inst_id = event.data.get("inst_id", "")

        if data and inst_id:
            self._orderbook_cache[inst_id] = data[0]
            self._update_count += 1
            self.metrics.update_activity()

            # 更新缓存元数据
            self._update_cache_metadata(inst_id)

    async def _on_kline_update(self, event: Event):
        """处理kline更新"""
        data = event.data.get("data", [])
        inst_id = event.data.get("inst_id", "")

        if data and inst_id:
            if inst_id not in self._kline_cache:
                self._kline_cache[inst_id] = []

            self._kline_cache[inst_id].extend(data)
            # 限制缓存大小
            if len(self._kline_cache[inst_id]) > self._max_cache_size:
                self._kline_cache[inst_id] = self._kline_cache[inst_id][
                    -self._max_cache_size :
                ]

            self._update_count += 1
            self.metrics.update_activity()

            # 更新缓存元数据
            self._update_cache_metadata(inst_id)

    async def _on_trade_update(self, event: Event):
        """处理trade更新"""
        data = event.data.get("data", [])
        inst_id = event.data.get("inst_id", "")

        if data and inst_id:
            if inst_id not in self._trade_cache:
                self._trade_cache[inst_id] = []

            self._trade_cache[inst_id].extend(data)
            # 限制缓存大小
            if len(self._trade_cache[inst_id]) > self._max_cache_size:
                self._trade_cache[inst_id] = self._trade_cache[inst_id][
                    -self._max_cache_size :
                ]

            self._update_count += 1
            self.metrics.update_activity()

            # 更新缓存元数据
            self._update_cache_metadata(inst_id)

    def _update_cache_metadata(self, inst_id: str):
        """更新缓存元数据"""
        import time

        current_time = time.time()

        if inst_id not in self._cache_metadata:
            self._cache_metadata[inst_id] = {}

        self._cache_metadata[inst_id]["last_access_time"] = current_time
        self._cache_metadata[inst_id]["last_update_time"] = current_time

    # ========== 公共接口 ==========

    async def subscribe_instrument(self, inst_id: str) -> bool:
        """
        订阅产品

        Args:
            inst_id: 产品ID

        Returns:
            bool: 是否订阅成功
        """
        if inst_id in self._subscribed_inst_ids:
            return True

        if not self.ws_client:
            logger.warning("WebSocket客户端未初始化")
            return False

        try:
            # 订阅ticker
            await self.ws_client.subscribe("tickers", inst_id)
            # 订阅orderbook
            await self.ws_client.subscribe("books", inst_id, lambda x: None)

            self._subscribed_inst_ids.add(inst_id)
            logger.info(f"订阅产品成功: {inst_id}")
            return True

        except Exception as e:
            logger.error(f"订阅产品失败 {inst_id}: {e}")
            return False

    async def unsubscribe_instrument(self, inst_id: str) -> bool:
        """
        取消订阅产品

        Args:
            inst_id: 产品ID

        Returns:
            bool: 是否取消成功
        """
        if inst_id not in self._subscribed_inst_ids:
            return True

        if not self.ws_client:
            return False

        try:
            await self.ws_client.unsubscribe("tickers", inst_id)
            await self.ws_client.unsubscribe("books", inst_id)

            self._subscribed_inst_ids.discard(inst_id)
            logger.info(f"取消订阅产品: {inst_id}")
            return True

        except Exception as e:
            logger.error(f"取消订阅失败 {inst_id}: {e}")
            return False

    def get_ticker(self, inst_id: str = None) -> Optional[Dict]:
        """
        获取ticker数据

        Args:
            inst_id: 产品ID

        Returns:
            Optional[Dict]: ticker数据
        """
        inst_id = inst_id or self._default_inst_id
        # 更新缓存元数据
        self._update_cache_metadata(inst_id)
        return self._ticker_cache.get(inst_id)

    def get_orderbook(self, inst_id: str = None) -> Optional[Dict]:
        """
        获取orderbook数据

        Args:
            inst_id: 产品ID

        Returns:
            Optional[Dict]: orderbook数据
        """
        inst_id = inst_id or self._default_inst_id
        # 更新缓存元数据
        self._update_cache_metadata(inst_id)
        return self._orderbook_cache.get(inst_id)

    def get_kline(self, inst_id: str = None, bar: str = "1m") -> List:
        """
        获取kline数据

        Args:
            inst_id: 产品ID
            bar: 时间粒度

        Returns:
            List: kline数据列表
        """
        inst_id = inst_id or self._default_inst_id
        # 更新缓存元数据
        self._update_cache_metadata(inst_id)
        return self._kline_cache.get(inst_id, [])

    def get_trades(self, inst_id: str = None) -> List:
        """
        获取trade数据

        Args:
            inst_id: 产品ID

        Returns:
            List: trade数据列表
        """
        inst_id = inst_id or self._default_inst_id
        # 更新缓存元数据
        self._update_cache_metadata(inst_id)
        return self._trade_cache.get(inst_id, [])

    def get_current_price(self, inst_id: str = None) -> Optional[float]:
        """
        获取当前价格

        Args:
            inst_id: 产品ID

        Returns:
            Optional[float]: 当前价格
        """
        ticker = self.get_ticker(inst_id)
        if ticker:
            last = ticker.get("last")
            return float(last) if last else None
        return None

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        base_status = super().get_status()
        base_status.update(
            {
                "subscribed_instruments": list(self._subscribed_inst_ids),
                "cache_sizes": {
                    "ticker": len(self._ticker_cache),
                    "orderbook": len(self._orderbook_cache),
                    "kline": len(self._kline_cache),
                    "trades": len(self._trade_cache),
                },
                "update_count": self._update_count,
            }
        )
        return base_status
