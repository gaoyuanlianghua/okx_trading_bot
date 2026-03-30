"""
基础交易所接口

定义统一的交易所接口，为不同交易所提供一致的操作方法
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import asyncio


class BaseExchange(ABC):
    """基础交易所接口"""
    
    def __init__(self, api_key: str = "", api_secret: str = "", passphrase: str = "", is_test: bool = False):
        """
        初始化交易所客户端
        
        Args:
            api_key: API密钥
            api_secret: API密钥密码
            passphrase: 密码短语
            is_test: 是否为测试环境
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.is_test = is_test
        self.name = "BaseExchange"
    
    @abstractmethod
    async def get_server_time(self) -> Optional[str]:
        """
        获取服务器时间
        
        Returns:
            Optional[str]: 服务器时间戳
        """
        pass
    
    @abstractmethod
    async def get_instruments(self, inst_type: str = "SWAP") -> List[Dict]:
        """
        获取交易产品信息
        
        Args:
            inst_type: 产品类型
            
        Returns:
            List[Dict]: 产品列表
        """
        pass
    
    @abstractmethod
    async def get_ticker(self, inst_id: str) -> Optional[Dict]:
        """
        获取单个产品的行情信息
        
        Args:
            inst_id: 产品ID
            
        Returns:
            Optional[Dict]: 行情数据
        """
        pass
    
    @abstractmethod
    async def get_orderbook(self, inst_id: str, depth: int = 5) -> Optional[Dict]:
        """
        获取订单簿
        
        Args:
            inst_id: 产品ID
            depth: 深度
            
        Returns:
            Optional[Dict]: 订单簿数据
        """
        pass
    
    @abstractmethod
    async def get_candles(self, inst_id: str, bar: str = "1m", limit: int = 100) -> List[List]:
        """
        获取K线数据
        
        Args:
            inst_id: 产品ID
            bar: 时间粒度
            limit: 数量限制
            
        Returns:
            List[List]: K线数据列表
        """
        pass
    
    @abstractmethod
    async def get_trades(self, inst_id: str, limit: int = 100) -> List[Dict]:
        """
        获取成交数据
        
        Args:
            inst_id: 产品ID
            limit: 数量限制
            
        Returns:
            List[Dict]: 成交数据列表
        """
        pass
    
    @abstractmethod
    async def get_account_balance(self, ccy: str = "") -> Optional[Dict]:
        """
        获取账户余额
        
        Args:
            ccy: 币种，为空则返回所有币种
            
        Returns:
            Optional[Dict]: 余额数据
        """
        pass
    
    @abstractmethod
    async def get_positions(self, inst_type: str = "", inst_id: str = "") -> List[Dict]:
        """
        获取持仓信息
        
        Args:
            inst_type: 产品类型
            inst_id: 产品ID
            
        Returns:
            List[Dict]: 持仓列表
        """
        pass
    
    @abstractmethod
    async def place_order(
        self,
        inst_id: str,
        side: str,
        ord_type: str,
        sz: str,
        px: str = "",
        td_mode: str = "cross",
    ) -> Optional[str]:
        """
        下单
        
        Args:
            inst_id: 产品ID
            side: 买卖方向 (buy/sell)
            ord_type: 订单类型 (market/limit/post_only/fok/ioc)
            sz: 委托数量
            px: 委托价格（市价单可不填）
            td_mode: 交易模式 (cross/isolated/cash)
            
        Returns:
            Optional[str]: 订单ID
        """
        pass
    
    @abstractmethod
    async def cancel_order(
        self, inst_id: str, ord_id: str = "", cl_ord_id: str = ""
    ) -> bool:
        """
        撤单
        
        Args:
            inst_id: 产品ID
            ord_id: 订单ID
            cl_ord_id: 客户自定义订单ID
            
        Returns:
            bool: 是否成功
        """
        pass
    
    @abstractmethod
    async def get_order_info(
        self, inst_id: str, ord_id: str = "", cl_ord_id: str = ""
    ) -> Optional[Dict]:
        """
        获取订单信息
        
        Args:
            inst_id: 产品ID
            ord_id: 订单ID
            cl_ord_id: 客户自定义订单ID
            
        Returns:
            Optional[Dict]: 订单信息
        """
        pass
    
    @abstractmethod
    async def get_pending_orders(
        self, inst_id: str = "", inst_type: str = ""
    ) -> List[Dict]:
        """
        获取未成交订单
        
        Args:
            inst_id: 产品ID
            inst_type: 产品类型
            
        Returns:
            List[Dict]: 订单列表
        """
        pass
    
    @abstractmethod
    async def get_order_history(
        self, inst_type: str, inst_id: str = "", limit: int = 100
    ) -> List[Dict]:
        """
        获取历史订单
        
        Args:
            inst_type: 产品类型
            inst_id: 产品ID
            limit: 数量限制
            
        Returns:
            List[Dict]: 订单列表
        """
        pass
    
    @abstractmethod
    async def batch_place_orders(self, orders: List[Dict]) -> List[Dict]:
        """
        批量下单
        
        Args:
            orders: 订单列表
            
        Returns:
            List[Dict]: 订单结果列表
        """
        pass
    
    @abstractmethod
    async def batch_cancel_orders(self, orders: List[Dict]) -> List[Dict]:
        """
        批量撤单
        
        Args:
            orders: 订单列表
            
        Returns:
            List[Dict]: 撤单结果列表
        """
        pass
    
    @abstractmethod
    async def close(self):
        """
        关闭客户端
        """
        pass
    
    async def batch_request(self, requests: List[Dict]) -> List[Optional[Dict]]:
        """
        批量发送API请求
        
        Args:
            requests: 请求列表
            
        Returns:
            List[Optional[Dict]]: 响应数据列表
        """
        tasks = []
        for req in requests:
            method = req.get("method")
            endpoint = req.get("endpoint")
            params = req.get("params")
            body = req.get("body")
            
            # 根据方法名动态调用
            if hasattr(self, method):
                task = getattr(self, method)(**params) if params else getattr(self, method)()
                tasks.append(task)
            else:
                tasks.append(asyncio.create_task(asyncio.sleep(0, result=None)))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(None)
            else:
                processed_results.append(result)
        
        return processed_results
