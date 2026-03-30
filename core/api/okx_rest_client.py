"""
OKX REST API客户端 - 处理HTTP请求
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode

from .base_exchange import BaseExchange
from .auth import OKXAuth
from core.utils.logger import get_logger

logger = get_logger(__name__)


class OKXRESTClient(BaseExchange):
    """
    OKX REST API客户端

    提供对OKX交易所REST API的访问
    """

    # API基础URL
    BASE_URL = "https://www.okx.com"
    # 模拟盘API基础URL
    BASE_URL_TEST = "https://www.okx.com"

    # API版本
    API_VERSION = "/api/v5"

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        is_test: bool = False,
        timeout: int = 30,
    ):
        """
        初始化REST客户端

        Args:
            api_key: API密钥
            api_secret: API密钥密码
            passphrase: 密码短语
            is_test: 是否为模拟盘
            timeout: 请求超时时间（秒）
        """
        # 调用父类初始化方法
        super().__init__(api_key, api_secret, passphrase, is_test)
        
        self.name = "OKX"
        self.is_test = is_test
        self.auth = OKXAuth(api_key, api_secret, passphrase, is_test)
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None

        # 请求限制
        self._request_count = 0
        self._last_reset = asyncio.get_event_loop().time()
        self._rate_limit = 20  # 每秒请求数限制

        # API调用记录
        self.api_call_history = []
        self.max_history_size = 1000  # 最大历史记录数

        # 本地缓存
        self._cache = {}  # 缓存字典
        self._cache_ttl = {}  # 缓存过期时间
        self._default_ttl = 60  # 默认缓存时间（秒）
        self._cache_size = 1000  # 最大缓存数量

        logger.info(f"REST客户端初始化完成 (模拟盘: {is_test})")

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={"User-Agent": "OKX-Trading-Bot/1.0"},
            )
        return self.session

    def _generate_cache_key(
        self, method: str, endpoint: str, params: Dict = None
    ) -> str:
        """生成缓存键"""
        key_parts = [method.upper(), endpoint]
        if params:
            # 对参数进行排序，确保相同参数顺序不同时生成相同的键
            sorted_params = sorted(params.items())
            key_parts.extend([f"{k}={v}" for k, v in sorted_params])
        return "|".join(key_parts)

    def _get_cache(self, key: str) -> Optional[Any]:
        """获取缓存"""
        import time

        current_time = time.time()

        # 检查缓存是否存在且未过期
        if key in self._cache and key in self._cache_ttl:
            if current_time < self._cache_ttl[key]:
                logger.debug(f"缓存命中: {key}")
                return self._cache[key]
            else:
                # 缓存过期，删除
                del self._cache[key]
                del self._cache_ttl[key]
                logger.debug(f"缓存过期: {key}")
        return None

    def _set_cache(self, key: str, value: Any, ttl: int = None):
        """设置缓存"""
        import time

        ttl = ttl or self._default_ttl
        current_time = time.time()

        # 检查缓存大小
        if len(self._cache) >= self._cache_size:
            # 删除最旧的缓存
            oldest_key = min(self._cache_ttl, key=lambda k: self._cache_ttl[k])
            del self._cache[oldest_key]
            del self._cache_ttl[oldest_key]
            logger.debug(f"缓存已满，删除最旧的缓存: {oldest_key}")

        # 设置缓存
        self._cache[key] = value
        self._cache_ttl[key] = current_time + ttl
        logger.debug(f"缓存设置: {key} (TTL: {ttl}秒)")

    def _clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._cache_ttl.clear()
        logger.debug("缓存已清空")

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

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Dict = None,
        body: Dict = None,
        auth_required: bool = True,
        caller: str = None,
        use_cache: bool = True,
        cache_ttl: int = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> Optional[Dict]:
        """
        发送HTTP请求

        Args:
            method: HTTP方法 (GET/POST/DELETE)
            endpoint: API端点
            params: URL参数
            body: 请求体
            auth_required: 是否需要认证
            caller: 调用者函数名
            use_cache: 是否使用缓存
            cache_ttl: 缓存过期时间（秒）
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）

        Returns:
            Optional[Dict]: 响应数据
        """
        import time
        import traceback

        # 获取调用者函数名
        if not caller:
            stack = traceback.extract_stack()
            if len(stack) > 2:
                caller = stack[-3][2]

        # 检查缓存（只对GET请求使用缓存）
        if use_cache and method.upper() == "GET" and not auth_required:
            cache_key = self._generate_cache_key(method, endpoint, params)
            cached_data = self._get_cache(cache_key)
            if cached_data is not None:
                # 缓存命中，直接返回
                start_time = time.time()
                api_call_record = {
                    "timestamp": time.time(),
                    "caller": caller,
                    "method": method.upper(),
                    "url": f"{self.BASE_URL}{self.API_VERSION}{endpoint}",
                    "endpoint": endpoint,
                    "params": params,
                    "body": body,
                    "response": {"data": cached_data},
                    "status_code": 200,
                    "response_time": time.time() - start_time,
                    "error": None,
                    "cached": True,
                    "retry_count": 0,
                }
                self.api_call_history.append(api_call_record)
                if len(self.api_call_history) > self.max_history_size:
                    self.api_call_history = self.api_call_history[
                        -self.max_history_size :
                    ]
                logger.debug(f"使用缓存数据: {endpoint}")
                return cached_data

        # 构建URL
        base_url = self.BASE_URL_TEST if self.is_test else self.BASE_URL
        url = f"{base_url}{self.API_VERSION}{endpoint}"
        if params:
            url += "?" + urlencode(params)

        # 构建请求体
        body_json = json.dumps(body) if body else ""

        # 构建请求头
        headers = {"Content-Type": "application/json"}
        if auth_required and self.auth.is_configured():
            request_path = f"{self.API_VERSION}{endpoint}"
            if params:
                request_path += "?" + urlencode(params)
            headers.update(self.auth.get_headers(method, request_path, body_json))

        # 记录请求信息
        logger.debug(f"API请求: {method.upper()} {url} (调用者: {caller})")
        if body:
            logger.debug(f"请求体: {body_json}")

        # 重试逻辑
        for retry in range(max_retries + 1):
            start_time = time.time()
            
            # 准备API调用记录
            api_call_record = {
                "timestamp": time.time(),
                "caller": caller,
                "method": method.upper(),
                "url": url,
                "endpoint": endpoint,
                "params": params,
                "body": body,
                "headers": headers,
                "response": None,
                "status_code": None,
                "response_time": None,
                "error": None,
                "cached": False,
                "retry_count": retry,
            }

            try:
                await self._check_rate_limit()
                session = await self._get_session()

                async with session.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    data=body_json if body_json else None,
                ) as response:

                    # 解析响应
                    text = await response.text()
                    response_time = time.time() - start_time

                    # 记录响应信息
                    logger.debug(
                        f"API响应: {response.status} {url} (耗时: {response_time:.3f}s) (调用者: {caller}) (重试: {retry}/{max_retries})"
                    )
                    logger.debug(f"响应体: {text}")

                    # 更新API调用记录
                    api_call_record["status_code"] = response.status
                    api_call_record["response_time"] = response_time

                    if response.status != 200:
                        error_msg = f"HTTP错误 {response.status}: {text}"
                        logger.error(error_msg)
                        api_call_record["error"] = error_msg
                        
                        # 对于网络错误和服务器错误，进行重试
                        if response.status >= 500 and retry < max_retries:
                            logger.warning(f"服务器错误，进行重试 ({retry + 1}/{max_retries})")
                            await asyncio.sleep(retry_delay * (retry + 1))
                            continue
                        return None

                    data = json.loads(text)
                    api_call_record["response"] = data

                    # 检查业务错误码
                    if data.get("code") != "0":
                        error_msg = f"API错误 {data.get('code')}: {data.get('msg')}"
                        logger.error(error_msg)
                        api_call_record["error"] = error_msg
                        
                        # 对于某些错误码，进行重试
                        retryable_codes = ["50000", "50001", "50002"]  # 服务器临时错误
                        if data.get("code") in retryable_codes and retry < max_retries:
                            logger.warning(f"API错误，进行重试 ({retry + 1}/{max_retries})")
                            await asyncio.sleep(retry_delay * (retry + 1))
                            continue
                        return None

                    response_data = data.get("data")

                    # 缓存响应数据（只对GET请求使用缓存）
                    if (
                        use_cache
                        and method.upper() == "GET"
                        and not auth_required
                        and response_data is not None
                    ):
                        cache_key = self._generate_cache_key(method, endpoint, params)
                        self._set_cache(cache_key, response_data, cache_ttl)

                    # 添加到API调用历史
                    self.api_call_history.append(api_call_record)
                    # 限制历史记录长度
                    if len(self.api_call_history) > self.max_history_size:
                        self.api_call_history = self.api_call_history[-self.max_history_size :]

                    return response_data

            except asyncio.TimeoutError:
                error_msg = f"请求超时: {url}"
                logger.error(error_msg)
                api_call_record["error"] = error_msg
                
                # 超时错误，进行重试
                if retry < max_retries:
                    logger.warning(f"请求超时，进行重试 ({retry + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay * (retry + 1))
                    continue
            except aiohttp.ClientError as e:
                error_msg = f"网络错误: {e}"
                logger.error(error_msg)
                api_call_record["error"] = error_msg
                
                # 网络错误，进行重试
                if retry < max_retries:
                    logger.warning(f"网络错误，进行重试 ({retry + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay * (retry + 1))
                    continue
            except Exception as e:
                error_msg = f"请求异常: {e}"
                logger.error(error_msg)
                api_call_record["error"] = error_msg
                
                # 其他异常，进行重试
                if retry < max_retries:
                    logger.warning(f"请求异常，进行重试 ({retry + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay * (retry + 1))
                    continue
            finally:
                # 添加到API调用历史
                self.api_call_history.append(api_call_record)
                # 限制历史记录长度
                if len(self.api_call_history) > self.max_history_size:
                    self.api_call_history = self.api_call_history[-self.max_history_size :]

        return None

    # ========== 公共API（无需认证）==========

    async def get_server_time(self) -> Optional[str]:
        """获取服务器时间"""
        result = await self.request("GET", "/public/time", auth_required=False)
        if result and len(result) > 0:
            return result[0].get("ts")
        return None

    async def get_instruments(self, inst_type: str = "SWAP") -> List[Dict]:
        """
        获取交易产品信息

        Args:
            inst_type: 产品类型 (SPOT/MARGIN/SWAP/FUTURES/OPTION)

        Returns:
            List[Dict]: 产品列表
        """
        result = await self.request(
            "GET",
            "/public/instruments",
            params={"instType": inst_type},
            auth_required=False,
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
            "GET", "/market/ticker", params={"instId": inst_id}, auth_required=False
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
            "GET",
            "/market/books",
            params={"instId": inst_id, "sz": str(depth)},
            auth_required=False,
        )
        if result and len(result) > 0:
            return result[0]
        return None

    async def get_candles(
        self, inst_id: str, bar: str = "1m", limit: int = 100
    ) -> List[List]:
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
            "GET",
            "/market/candles",
            params={"instId": inst_id, "bar": bar, "limit": str(limit)},
            auth_required=False,
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
            "GET",
            "/market/trades",
            params={"instId": inst_id, "limit": str(limit)},
            auth_required=False,
        )
        return result or []

    # ========== 私有API（需要认证）==========

    async def get_account_balance(self, ccy: str = "") -> Optional[Dict]:
        """
        获取账户余额

        Args:
            ccy: 币种，为空则返回所有币种

        Returns:
            Optional[Dict]: 余额数据
        """
        params = {}
        if ccy:
            params["ccy"] = ccy

        result = await self.request("GET", "/account/balance", params=params)
        if result and len(result) > 0:
            return result[0]
        return None

    async def get_positions(self, inst_type: str = "", inst_id: str = "") -> List[Dict]:
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
            params["instType"] = inst_type
        if inst_id:
            params["instId"] = inst_id

        result = await self.request("GET", "/account/positions", params=params)
        return result or []

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
        body = {
            "instId": inst_id,
            "tdMode": td_mode,
            "side": side,
            "ordType": ord_type,
            "sz": sz,
        }

        if px and ord_type != "market":
            body["px"] = px

        result = await self.request("POST", "/trade/order", body=body)
        if result and len(result) > 0:
            return result[0].get("ordId")
        return None

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
        body = {"instId": inst_id}

        if ord_id:
            body["ordId"] = ord_id
        elif cl_ord_id:
            body["clOrdId"] = cl_ord_id
        else:
            logger.error("必须提供ordId或clOrdId")
            return False

        result = await self.request("POST", "/trade/cancel-order", body=body)
        return result is not None

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
        params = {"instId": inst_id}

        if ord_id:
            params["ordId"] = ord_id
        elif cl_ord_id:
            params["clOrdId"] = cl_ord_id

        result = await self.request("GET", "/trade/order", params=params)
        if result and len(result) > 0:
            return result[0]
        return None

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
        params = {}
        if inst_id:
            params["instId"] = inst_id
        if inst_type:
            params["instType"] = inst_type

        result = await self.request("GET", "/trade/orders-pending", params=params)
        return result or []

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
        params = {"instType": inst_type, "limit": str(limit)}
        if inst_id:
            params["instId"] = inst_id

        result = await self.request("GET", "/trade/orders-history", params=params)
        return result or []

    async def batch_place_orders(self, orders: List[Dict]) -> List[Dict]:
        """
        批量下单

        Args:
            orders: 订单列表，每个订单包含instId, tdMode, side, ordType, sz等字段

        Returns:
            List[Dict]: 订单结果列表
        """
        result = await self.request(
            "POST", "/trade/batch-order", body={"orders": orders}
        )
        return result or []

    async def batch_cancel_orders(self, orders: List[Dict]) -> List[Dict]:
        """
        批量撤单

        Args:
            orders: 订单列表，每个订单包含instId和ordId或clOrdId

        Returns:
            List[Dict]: 撤单结果列表
        """
        result = await self.request(
            "POST", "/trade/batch-cancel-orders", body={"orders": orders}
        )
        return result or []

    async def batch_amend_orders(self, orders: List[Dict]) -> List[Dict]:
        """
        批量改单

        Args:
            orders: 订单列表，每个订单包含instId, ordId或clOrdId，以及要修改的字段

        Returns:
            List[Dict]: 改单结果列表
        """
        result = await self.request(
            "POST", "/trade/batch-amend-orders", body={"orders": orders}
        )
        return result or []

    async def get_account_rate_limit(self) -> Optional[Dict]:
        """
        获取账户限速信息

        Returns:
            Optional[Dict]: 账户限速信息
        """
        result = await self.request("GET", "/account/rate-limit")
        if result and len(result) > 0:
            return result[0]
        return None

    async def batch_request(self, requests: List[Dict]) -> List[Optional[Dict]]:
        """
        批量发送API请求

        Args:
            requests: 请求列表，每个请求包含method, endpoint, params, body, auth_required, caller字段

        Returns:
            List[Optional[Dict]]: 响应数据列表
        """
        # 并发执行所有请求
        tasks = []
        for req in requests:
            task = self.request(
                method=req.get("method", "GET"),
                endpoint=req.get("endpoint"),
                params=req.get("params"),
                body=req.get("body"),
                auth_required=req.get("auth_required", True),
                caller=req.get("caller"),
            )
            tasks.append(task)

        # 使用gather并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"批量请求错误 [{i}]: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)

        return processed_results

    async def close(self):
        """关闭客户端"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("REST客户端已关闭")
