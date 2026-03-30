"""
交易所管理器

管理不同的交易所客户端，提供统一的接口来访问不同的交易所
"""

from typing import Dict, Optional, Type
from core.api.base_exchange import BaseExchange
from core.api.okx_rest_client import OKXRESTClient
from core.api.okx_websocket_client import OKXWebSocketClient
from core.utils.logger import get_logger

logger = get_logger(__name__)


class ExchangeManager:
    """
    交易所管理器
    
    管理不同的交易所客户端，提供统一的接口来访问不同的交易所
    """
    
    def __init__(self):
        """初始化交易所管理器"""
        self._exchanges: Dict[str, BaseExchange] = {}
        self._websocket_clients: Dict[str, OKXWebSocketClient] = {}
        self._exchange_classes: Dict[str, Type[BaseExchange]] = {
            "okx": OKXRESTClient,
            # 可以添加其他交易所的类
            # "binance": BinanceRESTClient,
            # "coinbase": CoinbaseRESTClient,
        }
    
    def get_exchange(self, exchange_name: str, **kwargs) -> Optional[BaseExchange]:
        """
        获取交易所客户端
        
        Args:
            exchange_name: 交易所名称
            **kwargs: 交易所客户端初始化参数
            
        Returns:
            Optional[BaseExchange]: 交易所客户端实例
        """
        if exchange_name not in self._exchanges:
            if exchange_name not in self._exchange_classes:
                logger.error(f"不支持的交易所: {exchange_name}")
                return None
            
            try:
                exchange_class = self._exchange_classes[exchange_name]
                exchange = exchange_class(**kwargs)
                self._exchanges[exchange_name] = exchange
                logger.info(f"创建交易所客户端: {exchange_name}")
            except Exception as e:
                logger.error(f"创建交易所客户端失败 {exchange_name}: {e}")
                return None
        
        return self._exchanges[exchange_name]
    
    def get_websocket_client(self, exchange_name: str, **kwargs) -> Optional[OKXWebSocketClient]:
        """
        获取WebSocket客户端
        
        Args:
            exchange_name: 交易所名称
            **kwargs: WebSocket客户端初始化参数
            
        Returns:
            Optional[OKXWebSocketClient]: WebSocket客户端实例
        """
        if exchange_name != "okx":
            logger.error(f"目前只支持OKX的WebSocket客户端: {exchange_name}")
            return None
        
        if exchange_name not in self._websocket_clients:
            try:
                websocket_client = OKXWebSocketClient(**kwargs)
                self._websocket_clients[exchange_name] = websocket_client
                logger.info(f"创建WebSocket客户端: {exchange_name}")
            except Exception as e:
                logger.error(f"创建WebSocket客户端失败 {exchange_name}: {e}")
                return None
        
        return self._websocket_clients[exchange_name]
    
    def register_exchange(self, exchange_name: str, exchange_class: Type[BaseExchange]):
        """
        注册新的交易所类
        
        Args:
            exchange_name: 交易所名称
            exchange_class: 交易所类
        """
        self._exchange_classes[exchange_name] = exchange_class
        logger.info(f"注册新交易所: {exchange_name}")
    
    async def close_all(self):
        """
        关闭所有交易所客户端
        """
        # 关闭REST客户端
        for exchange_name, exchange in self._exchanges.items():
            try:
                await exchange.close()
                logger.info(f"关闭交易所客户端: {exchange_name}")
            except Exception as e:
                logger.error(f"关闭交易所客户端失败 {exchange_name}: {e}")
        
        # 关闭WebSocket客户端
        for exchange_name, websocket_client in self._websocket_clients.items():
            try:
                await websocket_client.close()
                logger.info(f"关闭WebSocket客户端: {exchange_name}")
            except Exception as e:
                logger.error(f"关闭WebSocket客户端失败 {exchange_name}: {e}")
        
        # 清空客户端列表
        self._exchanges.clear()
        self._websocket_clients.clear()
    
    def list_exchanges(self) -> list:
        """
        列出所有支持的交易所
        
        Returns:
            list: 支持的交易所列表
        """
        return list(self._exchange_classes.keys())
    
    def list_active_exchanges(self) -> list:
        """
        列出所有活跃的交易所客户端
        
        Returns:
            list: 活跃的交易所客户端列表
        """
        return list(self._exchanges.keys())


# 创建全局交易所管理器实例
exchange_manager = ExchangeManager()