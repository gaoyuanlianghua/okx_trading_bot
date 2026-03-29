"""
OKX REST API客户端 - 处理HTTP请求
"""
import asyncio
import aiohttp
import json
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode

from .auth import OKXAuth

logger = logging.getLogger(__name__)


class OKXRESTClient:
    """
    OKX REST API客户端
    
    提供对OKX交易所REST API的访问
    """
    
    # API基础URL
    BASE_URL = 'https://www.okx.com'
    
    # API版本
    API_VERSION = '/api/v5'
    
    def __init__(self, api_key: str = '', api_secret: str = '', 
                 passphrase: str = '', is_test: bool = False,
                 timeout: int = 30):
        """
        初始化REST客户端
        
        Args:
            api_key: API密钥
            api_secret: API密钥密码
            passphrase: 密码短语
            is_test: 是否为模拟盘
            timeout: 请求超时时间（秒）
        """
        self.auth = OKXAuth(api_key, api_secret, passphrase, is_test)
        self.is_test = is_test
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 请求限制
        self._request_count = 0
        self._last_reset = asyncio.get_event_loop().time()
        self._rate_limit = 20  # 每秒请求数限制
        
        logger.info(f"REST客户端初始化完成 (模拟盘: {is_test})")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={'User-Agent': 'OKX-Trading-Bot/1.0'}
            )
        return self.session
    
    async def _check_rate_limit(self):
        """检查并等待速率限制"""
        current_time = asyncio.get_event_loop().time()
        
        # 每秒重置计数
        if current_time - self._last_reset >= 1:
            self._request_count = 0
            self._last_reset = current_time
        
        # 检查是否超过限制
        if self._request_count >= self._rate_limit:
            wait_time = 1 - (current_time - self._last_reset)
            if wait_time > 0:
                logger.debug(f"速率限制等待: {wait_time:.2f}秒")
                await asyncio.sleep(wait_time)
                self._request_count = 0
                self._last_reset = asyncio.get_event_loop().time()
        
        self._request_count += 1
    
    async def request(self, method: str, endpoint: str, 
                     params: Dict = None, body: Dict = None,
                     auth_required: bool = True) -> Optional[Dict]:
        """
        发送HTTP请求
        
        Args:
            method: HTTP方法 (GET/POST/DELETE)
            endpoint: API端点
            params: URL参数
            body: 请求体
            auth_required: 是否需要认证
            
        Returns:
            Optional[Dict]: 响应数据
        """
        import time
        start_time = time.time()
        
        await self._check_rate_limit()
        
        # 构建URL
        url = f"{self.BASE_URL}{self.API_VERSION}{endpoint}"
        if params:
            url += '?' + urlencode(params)
        
        # 构建请求体
        body_json = json.dumps(body) if body else ''
        
        # 构建请求头
        headers = {'Content-Type': 'application/json'}
        if auth_required and self.auth.is_configured():
            request_path = f"{self.API_VERSION}{endpoint}"
            if params:
                request_path += '?' + urlencode(params)
            headers.update(self.auth.get_headers(method, request_path, body_json))
        
        # 记录请求信息
        logger.debug(f"API请求: {method.upper()} {url}")
        if body:
            logger.debug(f"请求体: {body_json}")
        
        try:
            session = await self._get_session()
            
            async with session.request(
                method=method.upper(),
                url=url,
                headers=headers,
                data=body_json if body_json else None
            ) as response:
                
                # 解析响应
                text = await response.text()
                response_time = time.time() - start_time
                
                # 记录响应信息
                logger.debug(f"API响应: {response.status} {url} (耗时: {response_time:.3f}s)")
                logger.debug(f"响应体: {text[:500]}{'...' if len(text) > 500 else ''}")
                
                if response.status != 200:
                    logger.error(f"HTTP错误 {response.status}: {text}")
                    return None
                
                data = json.loads(text)
                
                # 检查业务错误码
                if data.get('code') != '0':
                    logger.error(f"API错误 {data.get('code')}: {data.get('msg')}")
                    return None
                
                return data.get('data')
                
        except asyncio.TimeoutError:
            logger.error(f"请求超时: {url}")
            return None
        except Exception as e:
            logger.error(f"请求异常: {e}")
            return None
    
    # ========== 公共API（无需认证）==========
    
    async def get_server_time(self) -> Optional[str]:
        """获取服务器时间"""
        result = await self.request('GET', '/public/time', auth_required=False)
        if result and len(result) > 0:
            return result[0].get('ts')
        return None
    
    async def get_instruments(self, inst_type: str = 'SWAP') -> List[Dict]:
        """
        获取交易产品信息
        
        Args:
            inst_type: 产品类型 (SPOT/MARGIN/SWAP/FUTURES/OPTION)
            
        Returns:
            List[Dict]: 产品列表
        """
        result = await self.request(
            'GET', 
            '/public/instruments',
            params={'instType': inst_type},
            auth_required=False
        )
        return result or []
    
    async def get_ticker(self, inst_id: str) -> Optional[Dict]:
        """
        获取单个产品的行情信息
        
        Args:
            inst_id: 产品ID，如 BTC-USDT-SWAP
            
        Returns:
            Optional[Dict]: 行情数据
        """
        result = await self.request(
            'GET',
            '/market/ticker',
            params={'instId': inst_id},
            auth_required=False
        )
        if result and len(result) > 0:
            return result[0]
        return None
    
    async def get_orderbook(self, inst_id: str, depth: int = 5) -> Optional[Dict]:
        """
        获取订单簿
        
        Args:
            inst_id: 产品ID
            depth: 深度 (1-400)
            
        Returns:
            Optional[Dict]: 订单簿数据
        """
        result = await self.request(
            'GET',
            '/market/books',
            params={'instId': inst_id, 'sz': str(depth)},
            auth_required=False
        )
        if result and len(result) > 0:
            return result[0]
        return None
    
    async def get_candles(self, inst_id: str, bar: str = '1m', 
                         limit: int = 100) -> List[List]:
        """
        获取K线数据
        
        Args:
            inst_id: 产品ID
            bar: 时间粒度 (1m/3m/5m/15m/30m/1H/2H/4H/6H/12H/1D/1W/1M)
            limit: 数量限制
            
        Returns:
            List[List]: K线数据列表
        """
        result = await self.request(
            'GET',
            '/market/candles',
            params={'instId': inst_id, 'bar': bar, 'limit': str(limit)},
            auth_required=False
        )
        return result or []
    
    async def get_trades(self, inst_id: str, limit: int = 100) -> List[Dict]:
        """
        获取成交数据
        
        Args:
            inst_id: 产品ID
            limit: 数量限制
            
        Returns:
            List[Dict]: 成交数据列表
        """
        result = await self.request(
            'GET',
            '/market/trades',
            params={'instId': inst_id, 'limit': str(limit)},
            auth_required=False
        )
        return result or []
    
    # ========== 私有API（需要认证）==========
    
    async def get_account_balance(self, ccy: str = '') -> Optional[Dict]:
        """
        获取账户余额
        
        Args:
            ccy: 币种，为空则返回所有币种
            
        Returns:
            Optional[Dict]: 余额数据
        """
        params = {}
        if ccy:
            params['ccy'] = ccy
        
        result = await self.request('GET', '/account/balance', params=params)
        if result and len(result) > 0:
            return result[0]
        return None
    
    async def get_positions(self, inst_type: str = '', inst_id: str = '') -> List[Dict]:
        """
        获取持仓信息
        
        Args:
            inst_type: 产品类型
            inst_id: 产品ID
            
        Returns:
            List[Dict]: 持仓列表
        """
        params = {}
        if inst_type:
            params['instType'] = inst_type
        if inst_id:
            params['instId'] = inst_id
        
        result = await self.request('GET', '/account/positions', params=params)
        return result or []
    
    async def place_order(self, inst_id: str, side: str, ord_type: str,
                         sz: str, px: str = '', 
                         td_mode: str = 'cross') -> Optional[str]:
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
        body = {
            'instId': inst_id,
            'tdMode': td_mode,
            'side': side,
            'ordType': ord_type,
            'sz': sz
        }
        
        if px and ord_type != 'market':
            body['px'] = px
        
        result = await self.request('POST', '/trade/order', body=body)
        if result and len(result) > 0:
            return result[0].get('ordId')
        return None
    
    async def cancel_order(self, inst_id: str, ord_id: str = '', 
                          cl_ord_id: str = '') -> bool:
        """
        撤单
        
        Args:
            inst_id: 产品ID
            ord_id: 订单ID
            cl_ord_id: 客户自定义订单ID
            
        Returns:
            bool: 是否成功
        """
        body = {'instId': inst_id}
        
        if ord_id:
            body['ordId'] = ord_id
        elif cl_ord_id:
            body['clOrdId'] = cl_ord_id
        else:
            logger.error("必须提供ordId或clOrdId")
            return False
        
        result = await self.request('POST', '/trade/cancel-order', body=body)
        return result is not None
    
    async def get_order_info(self, inst_id: str, ord_id: str = '',
                            cl_ord_id: str = '') -> Optional[Dict]:
        """
        获取订单信息
        
        Args:
            inst_id: 产品ID
            ord_id: 订单ID
            cl_ord_id: 客户自定义订单ID
            
        Returns:
            Optional[Dict]: 订单信息
        """
        params = {'instId': inst_id}
        
        if ord_id:
            params['ordId'] = ord_id
        elif cl_ord_id:
            params['clOrdId'] = cl_ord_id
        
        result = await self.request('GET', '/trade/order', params=params)
        if result and len(result) > 0:
            return result[0]
        return None
    
    async def get_pending_orders(self, inst_id: str = '', 
                                inst_type: str = '') -> List[Dict]:
        """
        获取未成交订单
        
        Args:
            inst_id: 产品ID
            inst_type: 产品类型
            
        Returns:
            List[Dict]: 订单列表
        """
        params = {}
        if inst_id:
            params['instId'] = inst_id
        if inst_type:
            params['instType'] = inst_type
        
        result = await self.request('GET', '/trade/orders-pending', params=params)
        return result or []
    
    async def get_order_history(self, inst_type: str, inst_id: str = '',
                               limit: int = 100) -> List[Dict]:
        """
        获取历史订单
        
        Args:
            inst_type: 产品类型
            inst_id: 产品ID
            limit: 数量限制
            
        Returns:
            List[Dict]: 订单列表
        """
        params = {'instType': inst_type, 'limit': str(limit)}
        if inst_id:
            params['instId'] = inst_id
        
        result = await self.request('GET', '/trade/orders-history', params=params)
        return result or []
    
    async def batch_place_orders(self, orders: List[Dict]) -> List[Dict]:
        """
        批量下单
        
        Args:
            orders: 订单列表，每个订单包含instId, tdMode, side, ordType, sz等字段
            
        Returns:
            List[Dict]: 订单结果列表
        """
        result = await self.request('POST', '/trade/batch-order', body={'orders': orders})
        return result or []
    
    async def batch_cancel_orders(self, orders: List[Dict]) -> List[Dict]:
        """
        批量撤单
        
        Args:
            orders: 订单列表，每个订单包含instId和ordId或clOrdId
            
        Returns:
            List[Dict]: 撤单结果列表
        """
        result = await self.request('POST', '/trade/batch-cancel-orders', body={'orders': orders})
        return result or []
    
    async def batch_amend_orders(self, orders: List[Dict]) -> List[Dict]:
        """
        批量改单
        
        Args:
            orders: 订单列表，每个订单包含instId, ordId或clOrdId，以及要修改的字段
            
        Returns:
            List[Dict]: 改单结果列表
        """
        result = await self.request('POST', '/trade/batch-amend-orders', body={'orders': orders})
        return result or []
    
    async def get_account_rate_limit(self) -> Optional[Dict]:
        """
        获取账户限速信息
        
        Returns:
            Optional[Dict]: 账户限速信息
        """
        result = await self.request('GET', '/account/rate-limit')
        if result and len(result) > 0:
            return result[0]
        return None
    
    async def close(self):
        """关闭客户端"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("REST客户端已关闭")
