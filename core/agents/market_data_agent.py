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
from core.api.okx_rest_client import OKXRESTClient
from core.api.okx_websocket_client import OKXWebSocketClient

logger = logging.getLogger(__name__)


class MarketDataAgent(BaseAgent):
    """
    市场数据智能体
    
    职责：
    1. 获取实时行情数据（ticker、orderbook、kline等）
    2. 管理WebSocket订阅
    3. 缓存市场数据
    4. 提供数据查询接口
    """
    
    def __init__(self, config: AgentConfig, 
                 rest_client: OKXRESTClient = None,
                 ws_client: OKXWebSocketClient = None):
        """
        初始化市场数据智能体
        
        Args:
            config: 智能体配置
            rest_client: REST API客户端
            ws_client: WebSocket客户端
        """
        super().__init__(config)
        
        # API客户端
        self.rest_client = rest_client
        self.ws_client = ws_client
        
        # 数据缓存
        self._ticker_cache: Dict[str, Dict] = {}
        self._orderbook_cache: Dict[str, Dict] = {}
        self._kline_cache: Dict[str, List] = {}
        self._trade_cache: Dict[str, List] = {}
        
        # 订阅管理
        self._subscribed_inst_ids: set = set()
        self._default_inst_id = 'BTC-USDT-SWAP'
        
        # 数据更新计数
        self._update_count = 0
        
        logger.info(f"市场数据智能体初始化完成: {self.agent_id}")
    
    async def _initialize(self):
        """初始化"""
        # 注册消息处理器
        self.register_message_handler(MessageType.REQUEST_DATA, self._handle_data_request)
        
        # 订阅市场数据事件 - 使用lambda包装以避免bound method问题
        self.event_bus.subscribe(EventType.MARKET_DATA_TICKER, self._on_ticker_update, async_callback=True)
        self.event_bus.subscribe(EventType.MARKET_DATA_ORDERBOOK, self._on_orderbook_update, async_callback=True)
        self.event_bus.subscribe(EventType.MARKET_DATA_KLINE, self._on_kline_update, async_callback=True)
        self.event_bus.subscribe(EventType.MARKET_DATA_TRADE, self._on_trade_update, async_callback=True)
        
        logger.info("市场数据智能体初始化完成")
    
    async def _cleanup(self):
        """清理"""
        # 取消所有订阅
        if self.ws_client:
            for inst_id in list(self._subscribed_inst_ids):
                await self.ws_client.unsubscribe('tickers', inst_id)
                await self.ws_client.unsubscribe('books', inst_id)
        
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
        
        # 等待一段时间
        await asyncio.sleep(5)
    
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
        data_type = payload.get('data_type')
        inst_id = payload.get('inst_id', self._default_inst_id)
        
        response_data = {}
        
        if data_type == 'ticker':
            response_data = self.get_ticker(inst_id)
        elif data_type == 'orderbook':
            response_data = self.get_orderbook(inst_id)
        elif data_type == 'kline':
            bar = payload.get('bar', '1m')
            response_data = self.get_kline(inst_id, bar)
        elif data_type == 'trades':
            response_data = self.get_trades(inst_id)
        
        # 发送响应
        response = Message.create_response(
            sender=self.agent_id,
            receiver=message.sender,
            request_message=message,
            payload={'data': response_data}
        )
        await self.send_message(response)
    
    async def _on_ticker_update(self, event: Event):
        """处理ticker更新"""
        data = event.data.get('data', [])
        inst_id = event.data.get('inst_id', '')
        
        if data and inst_id:
            self._ticker_cache[inst_id] = data[0]
            self._update_count += 1
            self.metrics.update_activity()
            
            logger.debug(f"Ticker更新: {inst_id}, 价格: {data[0].get('last')}")
    
    async def _on_orderbook_update(self, event: Event):
        """处理orderbook更新"""
        data = event.data.get('data', [])
        inst_id = event.data.get('inst_id', '')
        
        if data and inst_id:
            self._orderbook_cache[inst_id] = data[0]
            self._update_count += 1
            self.metrics.update_activity()
    
    async def _on_kline_update(self, event: Event):
        """处理kline更新"""
        data = event.data.get('data', [])
        inst_id = event.data.get('inst_id', '')
        
        if data and inst_id:
            if inst_id not in self._kline_cache:
                self._kline_cache[inst_id] = []
            
            self._kline_cache[inst_id].extend(data)
            # 限制缓存大小
            if len(self._kline_cache[inst_id]) > 1000:
                self._kline_cache[inst_id] = self._kline_cache[inst_id][-1000:]
            
            self._update_count += 1
            self.metrics.update_activity()
    
    async def _on_trade_update(self, event: Event):
        """处理trade更新"""
        data = event.data.get('data', [])
        inst_id = event.data.get('inst_id', '')
        
        if data and inst_id:
            if inst_id not in self._trade_cache:
                self._trade_cache[inst_id] = []
            
            self._trade_cache[inst_id].extend(data)
            # 限制缓存大小
            if len(self._trade_cache[inst_id]) > 1000:
                self._trade_cache[inst_id] = self._trade_cache[inst_id][-1000:]
            
            self._update_count += 1
            self.metrics.update_activity()
    
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
            await self.ws_client.subscribe('tickers', inst_id)
            # 订阅orderbook
            await self.ws_client.subscribe('books', inst_id, lambda x: None)
            
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
            await self.ws_client.unsubscribe('tickers', inst_id)
            await self.ws_client.unsubscribe('books', inst_id)
            
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
        return self._orderbook_cache.get(inst_id)
    
    def get_kline(self, inst_id: str = None, bar: str = '1m') -> List:
        """
        获取kline数据
        
        Args:
            inst_id: 产品ID
            bar: 时间粒度
            
        Returns:
            List: kline数据列表
        """
        inst_id = inst_id or self._default_inst_id
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
            last = ticker.get('last')
            return float(last) if last else None
        return None
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        base_status = super().get_status()
        base_status.update({
            'subscribed_instruments': list(self._subscribed_inst_ids),
            'cache_sizes': {
                'ticker': len(self._ticker_cache),
                'orderbook': len(self._orderbook_cache),
                'kline': len(self._kline_cache),
                'trades': len(self._trade_cache)
            },
            'update_count': self._update_count
        })
        return base_status
