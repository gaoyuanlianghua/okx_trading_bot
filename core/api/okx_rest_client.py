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
from core.config.env_manager import env_manager

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
    # 备选API端点
    ALTERNATIVE_ENDPOINTS = [
        "https://www.okx.com",  # 主端点
        "https://okx.com",      # 备选端点1
        "https://api.okx.com",   # 备选端点2
    ]

    # API版本
    API_VERSION = "/api/v5"

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        is_test: bool = False,
        timeout: int = 30,
        use_env_config: bool = False,
    ):
        """
        初始化REST客户端

        Args:
            api_key: API密钥
            api_secret: API密钥密码
            passphrase: 密码短语
            is_test: 是否为模拟盘
            timeout: 请求超时时间（秒）
            use_env_config: 是否使用环境配置
        """
        # 从环境配置获取参数
        if use_env_config:
            api_config = env_manager.get_api_config()
            api_key = api_config.get('api_key', api_key)
            api_secret = api_config.get('api_secret', api_secret)
            passphrase = api_config.get('passphrase', passphrase)
            is_test = api_config.get('is_test', is_test)
            timeout = api_config.get('timeout', timeout)
            logger.info("从环境配置获取API参数")
        
        # 调用父类初始化方法
        super().__init__(api_key, api_secret, passphrase, is_test)
        
        self.name = "OKX"
        self.is_test = is_test
        self.auth = OKXAuth(api_key, api_secret, passphrase, is_test)
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 时间戳同步
        asyncio.ensure_future(self.sync_time())

        # 请求限制
        self._request_count = 0
        self._last_reset = asyncio.get_event_loop().time()
        self._rate_limit = 20  # 每秒请求数限制
        self._burst_limit = 60  # 每分钟请求数限制
        self._burst_count = 0
        self._burst_reset = asyncio.get_event_loop().time()

        # API调用记录
        self.api_call_history = []
        self.max_history_size = 1000  # 最大历史记录数

        # 本地缓存
        self._cache = {}  # 缓存字典
        self._cache_ttl = {}  # 缓存过期时间
        self._default_ttl = 60  # 默认缓存时间（秒）
        self._cache_size = 1000  # 最大缓存数量
        self._cache_ttl_by_endpoint = {
            # 公共API缓存时间（秒）
            "/public/time": 10,  # 服务器时间，更新频繁
            "/public/instruments": 3600,  # 交易产品信息，更新较少
            "/market/ticker": 5,  # 行情数据，更新频繁
            "/market/books": 2,  # 订单簿，更新频繁
            "/market/candles": 5,  # K线数据，更新频繁
            "/market/trades": 3,  # 成交数据，更新频繁
            # 私有API缓存时间（秒）
            "/account/balance": 10,  # 账户余额，更新中等
            "/account/positions": 5,  # 持仓信息，更新频繁
            "/trade/orders-pending": 3,  # 未成交订单，更新频繁
        }

        # API调用统计
        self.api_stats = {
            'total_calls': 0,
            'success_calls': 0,
            'failed_calls': 0,
            'cached_calls': 0,
            'avg_response_time': 0,
            'total_response_time': 0,
            'endpoint_stats': {}  # 按端点统计
        }

        # 批量请求队列
        self._batch_queue = {}  # 按端点分组的批量请求
        self._batch_timer = None  # 批量请求定时器
        self._batch_interval = 0.1  # 批量请求间隔（秒）

        logger.info(f"REST客户端初始化完成 (模拟盘: {is_test})")

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self.session is None or self.session.closed:
            # 配置安全的HTTP会话
            connector = aiohttp.TCPConnector(
                ssl=True,  # 启用SSL验证
                verify_ssl=True,  # 验证SSL证书
                limit=100,  # 限制并发连接数
                limit_per_host=20,  # 每个主机的连接限制
            )
            
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={"User-Agent": "OKX-Trading-Bot/1.0"},
                connector=connector,
                cookie_jar=aiohttp.DummyCookieJar(),  # 不存储cookies
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

        # 每分钟重置计数
        if current_time - self._burst_reset >= 60:
            self._burst_count = 0
            self._burst_reset = current_time

        # 检查是否超过每分钟限制
        if self._burst_count >= self._burst_limit:
            wait_time = 60 - (current_time - self._burst_reset)
            if wait_time > 0:
                logger.debug(f"突发速率限制等待: {wait_time:.2f}秒")
                await asyncio.sleep(wait_time)
                self._burst_count = 0
                self._burst_reset = current_time

        # 检查是否超过每秒限制
        if self._request_count >= self._rate_limit:
            wait_time = 1 - (current_time - self._last_reset)
            if wait_time > 0:
                logger.debug(f"速率限制等待: {wait_time:.2f}秒")
                await asyncio.sleep(wait_time)
                self._request_count = 0
                self._last_reset = current_time

        self._request_count += 1
        self._burst_count += 1

    def _validate_request_params(self, method: str, endpoint: str, params: Dict, body: Dict):
        """验证请求参数"""
        # 验证HTTP方法
        valid_methods = ["GET", "POST", "DELETE"]
        if method.upper() not in valid_methods:
            raise ValueError(f"无效的HTTP方法: {method}")
        
        # 验证端点
        if not endpoint.startswith("/"):
            raise ValueError(f"端点必须以/开头: {endpoint}")
        
        # 验证参数类型
        if params is not None and not isinstance(params, dict):
            raise ValueError("params必须是字典类型")
        
        if body is not None and not isinstance(body, dict):
            raise ValueError("body必须是字典类型")
        
        # 验证敏感参数
        if body and any(key in body for key in ["api_key", "secret", "passphrase"]):
            logger.warning("请求体中包含敏感信息")

    def _validate_response_data(self, data: Dict) -> bool:
        """验证响应数据"""
        if not isinstance(data, dict):
            return False
        
        # 检查响应格式
        if "data" not in data:
            return False
        
        # 按照OKX API指南检查错误码
        if "sCode" in data:
            # 当返回中有sCode字段时，使用sCode
            if data.get("sCode") != "0":
                logger.error(f"API错误: {data.get('sCode')} - {data.get('sMsg', '未知错误')}")
                return False
        else:
            # 当返回中没有sCode字段时，使用code
            if "code" not in data or data.get("code") != "0":
                logger.error(f"API错误: {data.get('code')} - {data.get('msg', '未知错误')}")
                return False
        
        return True

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

        try:
            # 验证请求参数
            self._validate_request_params(method, endpoint, params, body)
        except ValueError as e:
            logger.error(f"请求参数验证失败: {e}")
            return None

        # 检查缓存（只对GET请求使用缓存）
        if use_cache and method.upper() == "GET" and not auth_required:
            cache_key = self._generate_cache_key(method, endpoint, params)
            cached_data = self._get_cache(cache_key)
            if cached_data is not None:
                # 缓存命中，直接返回
                start_time = time.time()
                response_time = time.time() - start_time
                
                # 更新API调用统计
                self.api_stats['total_calls'] += 1
                self.api_stats['cached_calls'] += 1
                if endpoint not in self.api_stats['endpoint_stats']:
                    self.api_stats['endpoint_stats'][endpoint] = {
                        'total': 0,
                        'success': 0,
                        'failed': 0,
                        'cached': 0,
                        'avg_response_time': 0,
                        'total_response_time': 0
                    }
                self.api_stats['endpoint_stats'][endpoint]['total'] += 1
                self.api_stats['endpoint_stats'][endpoint]['cached'] += 1
                
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
                    "response_time": response_time,
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

        # 尝试所有可用的API端点
        for endpoint_idx, base_url in enumerate([self.BASE_URL] + self.ALTERNATIVE_ENDPOINTS):
            if self.is_test:
                base_url = self.BASE_URL_TEST
            
            # 构建URL
            url = f"{base_url}{self.API_VERSION}{endpoint}"
            if params:
                url += "?" + urlencode(params)

            # 构建请求体
            body_json = json.dumps(body) if body else ""

            # 构建请求头
            headers = {"Content-Type": "application/json"}
            # 模拟盘请求头
            if self.is_test:
                headers["x-simulated-trading"] = "1"
            if auth_required and self.auth.is_configured():
                # 签名时request_path应包含API版本
                request_path = f"{self.API_VERSION}{endpoint}"
                if params:
                    request_path += "?" + urlencode(params)
                headers.update(self.auth.get_headers(method, request_path, body_json))

            # 记录请求信息
            logger.info(f"API请求: {method.upper()} {url} (调用者: {caller}, 端点: {endpoint_idx+1}/{len([self.BASE_URL] + self.ALTERNATIVE_ENDPOINTS)})")
            if body:
                # 屏蔽敏感信息
                safe_body = {k: v for k, v in body.items() if k not in ["api_key", "secret", "passphrase"]}
                logger.info(f"请求体: {json.dumps(safe_body)}")

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
                        logger.info(
                            f"API响应: {response.status} {url} (耗时: {response_time:.3f}s) (调用者: {caller}) (重试: {retry}/{max_retries})"
                        )
                        logger.info(f"响应体: {text}")

                        # 更新API调用记录
                        api_call_record["status_code"] = response.status
                        api_call_record["response_time"] = response_time

                        if response.status != 200:
                            error_msg = f"HTTP错误 {response.status}: {text}"
                            logger.error(error_msg)
                            logger.error(f"详细响应: {text}")
                            api_call_record["error"] = error_msg
                            
                            # 对于网络错误和服务器错误，进行重试
                            if response.status >= 500 and retry < max_retries:
                                logger.warning(f"服务器错误，进行重试 ({retry + 1}/{max_retries})")
                                await asyncio.sleep(retry_delay * (retry + 1))
                                continue
                            # 如果是当前端点的最后一次重试，则尝试下一个端点
                            if retry == max_retries and endpoint_idx < len([self.BASE_URL] + self.ALTERNATIVE_ENDPOINTS) - 1:
                                logger.warning(f"当前端点 {base_url} 失败，尝试下一个端点")
                                break
                            # 更新API调用统计
                            self.api_stats['total_calls'] += 1
                            self.api_stats['failed_calls'] += 1
                            if endpoint not in self.api_stats['endpoint_stats']:
                                self.api_stats['endpoint_stats'][endpoint] = {
                                    'total': 0,
                                    'success': 0,
                                    'failed': 0,
                                    'cached': 0,
                                    'avg_response_time': 0,
                                    'total_response_time': 0
                                }
                            self.api_stats['endpoint_stats'][endpoint]['total'] += 1
                            self.api_stats['endpoint_stats'][endpoint]['failed'] += 1
                            return None

                        try:
                            data = json.loads(text)
                            api_call_record["response"] = data

                            # 检查业务错误码
                            # 按照OKX API指南处理返回数据
                            if "sCode" in data:
                                # 当返回中有sCode字段时，使用sCode和sMsg
                                if data.get("sCode") != "0":
                                    error_msg = f"API错误 {data.get('sCode')}: {data.get('sMsg')}"
                                    logger.error(error_msg)
                                    api_call_record["error"] = error_msg
                                    
                                    # 对于某些错误码，进行重试
                                    retryable_codes = ["50000", "50001", "50002"]  # 服务器临时错误
                                    if data.get("sCode") in retryable_codes and retry < max_retries:
                                        logger.warning(f"API错误，进行重试 ({retry + 1}/{max_retries})")
                                        await asyncio.sleep(retry_delay * (retry + 1))
                                        continue
                                    # 如果是当前端点的最后一次重试，则尝试下一个端点
                                    if retry == max_retries and endpoint_idx < len([self.BASE_URL] + self.ALTERNATIVE_ENDPOINTS) - 1:
                                        logger.warning(f"当前端点 {base_url} 失败，尝试下一个端点")
                                        break
                                    # 更新API调用统计
                                    self.api_stats['total_calls'] += 1
                                    self.api_stats['failed_calls'] += 1
                                    if endpoint not in self.api_stats['endpoint_stats']:
                                        self.api_stats['endpoint_stats'][endpoint] = {
                                            'total': 0,
                                            'success': 0,
                                            'failed': 0,
                                            'cached': 0,
                                            'avg_response_time': 0,
                                            'total_response_time': 0
                                        }
                                    self.api_stats['endpoint_stats'][endpoint]['total'] += 1
                                    self.api_stats['endpoint_stats'][endpoint]['failed'] += 1
                                    return None
                            else:
                                # 当返回中没有sCode字段时，使用code和msg
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
                                    # 如果是当前端点的最后一次重试，则尝试下一个端点
                                    if retry == max_retries and endpoint_idx < len([self.BASE_URL] + self.ALTERNATIVE_ENDPOINTS) - 1:
                                        logger.warning(f"当前端点 {base_url} 失败，尝试下一个端点")
                                        break
                                    # 更新API调用统计
                                    self.api_stats['total_calls'] += 1
                                    self.api_stats['failed_calls'] += 1
                                    if endpoint not in self.api_stats['endpoint_stats']:
                                        self.api_stats['endpoint_stats'][endpoint] = {
                                            'total': 0,
                                            'success': 0,
                                            'failed': 0,
                                            'cached': 0,
                                            'avg_response_time': 0,
                                            'total_response_time': 0
                                        }
                                    self.api_stats['endpoint_stats'][endpoint]['total'] += 1
                                    self.api_stats['endpoint_stats'][endpoint]['failed'] += 1
                                    return None
                        except json.JSONDecodeError as e:
                            error_msg = f"JSON解析错误: {e}"
                            logger.error(error_msg)
                            logger.error(f"响应体: {text}")
                            api_call_record["error"] = error_msg
                            # 如果是当前端点的最后一次重试，则尝试下一个端点
                            if retry == max_retries and endpoint_idx < len([self.BASE_URL] + self.ALTERNATIVE_ENDPOINTS) - 1:
                                logger.warning(f"当前端点 {base_url} 失败，尝试下一个端点")
                                break
                            # 更新API调用统计
                            self.api_stats['total_calls'] += 1
                            self.api_stats['failed_calls'] += 1
                            if endpoint not in self.api_stats['endpoint_stats']:
                                self.api_stats['endpoint_stats'][endpoint] = {
                                    'total': 0,
                                    'success': 0,
                                    'failed': 0,
                                    'cached': 0,
                                    'avg_response_time': 0,
                                    'total_response_time': 0
                                }
                            self.api_stats['endpoint_stats'][endpoint]['total'] += 1
                            self.api_stats['endpoint_stats'][endpoint]['failed'] += 1
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
                            # 使用端点特定的缓存时间
                            endpoint_ttl = self._cache_ttl_by_endpoint.get(endpoint, self._default_ttl)
                            self._set_cache(cache_key, response_data, endpoint_ttl)

                        # 更新API调用统计
                        self.api_stats['total_calls'] += 1
                        self.api_stats['success_calls'] += 1
                        self.api_stats['total_response_time'] += response_time
                        if self.api_stats['success_calls'] > 0:
                            self.api_stats['avg_response_time'] = self.api_stats['total_response_time'] / self.api_stats['success_calls']
                        
                        if endpoint not in self.api_stats['endpoint_stats']:
                            self.api_stats['endpoint_stats'][endpoint] = {
                                'total': 0,
                                'success': 0,
                                'failed': 0,
                                'cached': 0,
                                'avg_response_time': 0,
                                'total_response_time': 0
                            }
                        self.api_stats['endpoint_stats'][endpoint]['total'] += 1
                        self.api_stats['endpoint_stats'][endpoint]['success'] += 1
                        self.api_stats['endpoint_stats'][endpoint]['total_response_time'] += response_time
                        if self.api_stats['endpoint_stats'][endpoint]['success'] > 0:
                            self.api_stats['endpoint_stats'][endpoint]['avg_response_time'] = \
                                self.api_stats['endpoint_stats'][endpoint]['total_response_time'] / \
                                self.api_stats['endpoint_stats'][endpoint]['success']

                        # 添加到API调用历史
                        self.api_call_history.append(api_call_record)
                        # 限制历史记录长度
                        if len(self.api_call_history) > self.max_history_size:
                            self.api_call_history = self.api_call_history[-self.max_history_size :]

                        # 如果成功，更新默认端点为当前端点
                        if base_url != self.BASE_URL and not self.is_test:
                            logger.info(f"切换默认API端点: {self.BASE_URL} -> {base_url}")
                            self.BASE_URL = base_url

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
                    # 如果是当前端点的最后一次重试，则尝试下一个端点
                    if retry == max_retries and endpoint_idx < len([self.BASE_URL] + self.ALTERNATIVE_ENDPOINTS) - 1:
                        logger.warning(f"当前端点 {base_url} 超时，尝试下一个端点")
                        break
                except aiohttp.ClientError as e:
                    error_msg = f"网络错误: {e}"
                    logger.error(error_msg)
                    api_call_record["error"] = error_msg
                    
                    # 网络错误，进行重试
                    if retry < max_retries:
                        logger.warning(f"网络错误，进行重试 ({retry + 1}/{max_retries})")
                        await asyncio.sleep(retry_delay * (retry + 1))
                        continue
                    # 如果是当前端点的最后一次重试，则尝试下一个端点
                    if retry == max_retries and endpoint_idx < len([self.BASE_URL] + self.ALTERNATIVE_ENDPOINTS) - 1:
                        logger.warning(f"当前端点 {base_url} 网络错误，尝试下一个端点")
                        break
                except Exception as e:
                    error_msg = f"请求异常: {e}"
                    logger.error(error_msg)
                    api_call_record["error"] = error_msg
                    
                    # 其他异常，进行重试
                    if retry < max_retries:
                        logger.warning(f"请求异常，进行重试 ({retry + 1}/{max_retries})")
                        await asyncio.sleep(retry_delay * (retry + 1))
                        continue
                    # 如果是当前端点的最后一次重试，则尝试下一个端点
                    if retry == max_retries and endpoint_idx < len([self.BASE_URL] + self.ALTERNATIVE_ENDPOINTS) - 1:
                        logger.warning(f"当前端点 {base_url} 异常，尝试下一个端点")
                        break
                finally:
                    # 添加到API调用历史
                    self.api_call_history.append(api_call_record)
                    # 限制历史记录长度
                    if len(self.api_call_history) > self.max_history_size:
                        self.api_call_history = self.api_call_history[-self.max_history_size :]

        # 更新API调用统计
        self.api_stats['total_calls'] += 1
        self.api_stats['failed_calls'] += 1
        if endpoint not in self.api_stats['endpoint_stats']:
            self.api_stats['endpoint_stats'][endpoint] = {
                'total': 0,
                'success': 0,
                'failed': 0,
                'cached': 0,
                'avg_response_time': 0,
                'total_response_time': 0
            }
        self.api_stats['endpoint_stats'][endpoint]['total'] += 1
        self.api_stats['endpoint_stats'][endpoint]['failed'] += 1

        return None

    # ========== 公共API（无需认证）==========

    async def get_server_time(self) -> Optional[str]:
        """获取服务器时间"""
        result = await self.request("GET", "/public/time", auth_required=False)
        if result and len(result) > 0:
            return result[0].get("ts")
        return None
    
    def get_api_time(self) -> float:
        """
        获取 API 时间
        
        Returns:
            float: API 时间戳
        """
        import asyncio
        import time
        
        try:
            # 创建一个新的事件循环来执行异步操作
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 执行异步的 get_server_time 方法
            ts = loop.run_until_complete(self.get_server_time())
            
            # 关闭事件循环
            loop.close()
            
            if ts:
                # 将字符串时间戳转换为浮点数
                return float(ts) / 1000  # OKX API 返回的时间戳是毫秒级的
            return time.time()
        except Exception as e:
            logger.error(f"获取 API 时间失败: {e}")
            return time.time()

    async def sync_time(self):
        """
        同步OKX服务器时间
        """
        import time
        
        try:
            # 获取OKX服务器时间
            server_time = await self.get_server_time()
            if server_time:
                # 计算时间偏移量
                server_timestamp = float(server_time) / 1000  # 转换为秒
                local_timestamp = time.time()
                time_offset = server_timestamp - local_timestamp
                
                # 设置时间偏移量
                self.auth.set_time_offset(time_offset)
                logger.info(f"时间同步完成，偏移量: {time_offset:.3f}秒")
            else:
                logger.warning("时间同步失败: 无法获取服务器时间")
        except Exception as e:
            logger.error(f"时间同步异常: {e}")

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

    async def get_margin_account_balance(self) -> Optional[Dict]:
        """
        获取杠杆账户余额

        Returns:
            Optional[Dict]: 杠杆账户余额数据
        """
        # 使用正确的API端点获取杠杆账户信息
        result = await self.request("GET", "/account/balance")
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

    async def get_positions_history(self, inst_type: str = "", inst_id: str = "", limit: int = 100) -> List[Dict]:
        """
        获取历史持仓信息

        Args:
            inst_type: 产品类型
            inst_id: 产品ID
            limit: 数量限制

        Returns:
            List[Dict]: 历史持仓列表
        """
        params = {}
        if inst_type:
            params["instType"] = inst_type
        if inst_id:
            params["instId"] = inst_id
        if limit:
            params["limit"] = str(limit)

        result = await self.request("GET", "/account/positions-history", params=params)
        return result or []

    async def get_account_risk(self) -> List[Dict]:
        """
        获取账户风险状态

        Returns:
            List[Dict]: 账户风险状态列表
        """
        result = await self.request("GET", "/account/risk")
        return result or []

    async def get_account_bills(self, ccy: str = "", type: str = "", limit: int = 100) -> List[Dict]:
        """
        获取账户账单详情

        Args:
            ccy: 币种
            type: 账单类型
            limit: 数量限制

        Returns:
            List[Dict]: 账户账单列表
        """
        params = {}
        if ccy:
            params["ccy"] = ccy
        if type:
            params["type"] = type
        if limit:
            params["limit"] = str(limit)

        result = await self.request("GET", "/account/bills", params=params)
        return result or []

    async def get_account_bills_archive(self, ccy: str = "", type: str = "", limit: int = 100, after: str = "", before: str = "") -> List[Dict]:
        """
        获取近三个月内账户账单详情

        Args:
            ccy: 币种
            type: 账单类型
            limit: 数量限制
            after: 开始时间戳
            before: 结束时间戳

        Returns:
            List[Dict]: 账户账单列表
        """
        params = {}
        if ccy:
            params["ccy"] = ccy
        if type:
            params["type"] = type
        if limit:
            params["limit"] = str(limit)
        if after:
            params["after"] = after
        if before:
            params["before"] = before

        result = await self.request("GET", "/account/bills-archive", params=params)
        return result or []

    async def request_bill_flow(self, ccy: str = "", type: str = "", start_date: str = "", end_date: str = "") -> Dict:
        """
        申请获取账单流水

        Args:
            ccy: 币种
            type: 账单类型
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            Dict: 申请结果
        """
        body = {}
        if ccy:
            body["ccy"] = ccy
        if type:
            body["type"] = type
        if start_date:
            body["startDate"] = start_date
        if end_date:
            body["endDate"] = end_date

        result = await self.request("POST", "/account/bills-flow", body=body)
        return result[0] if result else {}

    async def get_bill_flow_status(self, bill_id: str) -> Dict:
        """
        获取账单流水状态

        Args:
            bill_id: 账单ID

        Returns:
            Dict: 账单流水状态
        """
        params = {"billId": bill_id}
        result = await self.request("GET", "/account/bills-flow", params=params)
        return result[0] if result else {}

    async def get_bill_types(self) -> List[Dict]:
        """
        获取账单类型

        Returns:
            List[Dict]: 账单类型列表
        """
        result = await self.request("GET", "/account/bill-types")
        return result or []

    async def get_account_config(self) -> List[Dict]:
        """
        获取账户配置

        Returns:
            List[Dict]: 账户配置列表
        """
        result = await self.request("GET", "/account/config")
        return result or []

    async def set_position_mode(self, pos_mode: str) -> Dict:
        """
        设置持仓模式

        Args:
            pos_mode: 持仓模式 (long_short_mode 或 net_mode)

        Returns:
            Dict: 设置结果
        """
        body = {"posMode": pos_mode}
        result = await self.request("POST", "/account/position-mode", body=body)
        return result[0] if result else {}

    async def set_leverage(self, inst_id: str, lever: str, mgn_mode: str) -> Optional[Dict]:
        """
        设置杠杆倍数

        Args:
            inst_id: 产品ID
            lever: 杠杆倍数
            mgn_mode: 保证金模式 (cross/isolated)

        Returns:
            Optional[Dict]: 设置结果
        """
        body = {
            "instId": inst_id,
            "lever": lever,
            "mgnMode": mgn_mode
        }

        result = await self.request("POST", "/account/set-leverage", body=body)
        return result or []

    async def get_max_order_size(self, inst_id: str, td_mode: str) -> List[Dict]:
        """
        获取最大可买卖/开仓数量

        Args:
            inst_id: 产品ID
            td_mode: 交易模式 (isolated/cross)

        Returns:
            List[Dict]: 最大订单大小信息
        """
        params = {
            "instId": inst_id,
            "tdMode": td_mode
        }

        result = await self.request("GET", "/account/max-size", params=params)
        return result or []

    async def get_max_avail_size(self, inst_id: str, td_mode: str) -> List[Dict]:
        """
        获取最大可用数量

        Args:
            inst_id: 产品ID
            td_mode: 交易模式 (cash/isolated/cross)

        Returns:
            List[Dict]: 最大可用数量信息
        """
        params = {
            "instId": inst_id,
            "tdMode": td_mode
        }

        result = await self.request("GET", "/account/max-avail-size", params=params)
        return result or []

    async def adjustment_margin(self, inst_id: str, pos_side: str, margin_type: str, amt: str) -> Dict:
        """
        调整保证金

        Args:
            inst_id: 产品ID
            pos_side: 持仓方向 (long/short)
            margin_type: 调整类型 (add/reduce)
            amt: 调整金额

        Returns:
            Dict: 调整结果
        """
        body = {
            "instId": inst_id,
            "posSide": pos_side,
            "type": margin_type,
            "amt": amt
        }

        result = await self.request("POST", "/account/position/margin", body=body)
        return result[0] if result else {}

    async def get_leverage(self, inst_id: str, mgn_mode: str) -> List[Dict]:
        """
        获取杠杆倍数

        Args:
            inst_id: 产品ID
            mgn_mode: 保证金模式 (cross/isolated)

        Returns:
            List[Dict]: 杠杆倍数信息
        """
        params = {
            "instId": inst_id,
            "mgnMode": mgn_mode
        }

        result = await self.request("GET", "/account/leverage", params=params)
        return result or []

    async def get_max_loan(self, inst_id: str, mgn_mode: str, mgn_ccy: str) -> List[Dict]:
        """
        获取币币杠杆最大可借数量

        Args:
            inst_id: 产品ID
            mgn_mode: 保证金模式 (cross/isolated)
            mgn_ccy: 保证金币种

        Returns:
            List[Dict]: 最大可借数量信息
        """
        params = {
            "instId": inst_id,
            "mgnMode": mgn_mode,
            "mgnCcy": mgn_ccy
        }

        result = await self.request("GET", "/account/max-loan", params=params)
        return result or []

    async def get_fee_rates(self, inst_type: str, inst_id: str) -> List[Dict]:
        """
        获取当前账户交易手续费费率

        Args:
            inst_type: 产品类型 (SPOT/SWAP/FUTURES/OPTIONS)
            inst_id: 产品ID

        Returns:
            List[Dict]: 手续费费率信息
        """
        params = {
            "instType": inst_type,
            "instId": inst_id
        }

        result = await self.request("GET", "/account/fee-rates", params=params)
        return result or []

    async def place_order(
        self,
        inst_id: str,
        side: str,
        ord_type: str,
        sz: str,
        px: str = "",
        td_mode: str = "cross",
        lever: str = "",
        tgtCcy: str = "",
        posSide: str = "",
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
            lever: 杠杆倍数（合约交易需要）
            tgtCcy: 交易货币类型，quote_ccy表示按USDT金额下单（仅用于买入）
            posSide: 持仓方向 (long/short)，合约交易需要

        Returns:
            Optional[str]: 订单ID
        """
        try:
            # 验证参数
            if not inst_id:
                logger.error("产品ID不能为空")
                return None
            if side not in ["buy", "sell"]:
                logger.error(f"无效的买卖方向: {side}")
                return None
            if ord_type not in ["market", "limit", "post_only", "fok", "ioc"]:
                logger.error(f"无效的订单类型: {ord_type}")
                return None
            if not sz:
                logger.error("委托数量不能为空")
                return None
            if ord_type != "market" and not px:
                logger.error("限价单必须提供价格")
                return None

            # 构建订单请求
            body = {
                "instId": inst_id,
                "tdMode": td_mode,
                "side": side,
                "ordType": ord_type,
                "ccy": "USDT",  # 添加 ccy 参数
            }

            # 对于现货交易，根据买卖方向设置不同的参数
            if "-" in inst_id and inst_id.split('-')[-1] == "USDT":
                if side == "buy":
                    # 买入时，sz表示USDT金额
                    body["sz"] = sz
                    # 买入时使用tgtCcy参数
                    if tgtCcy:
                        body["tgtCcy"] = tgtCcy
                else:
                    # 卖出时，sz表示BTC数量，不使用tgtCcy参数
                    body["sz"] = sz
            else:
                # 其他产品类型
                body["sz"] = sz
                if tgtCcy:
                    body["tgtCcy"] = tgtCcy

            if px and ord_type != "market":
                body["px"] = px

            if lever:
                body["lever"] = lever

            if posSide:
                body["posSide"] = posSide

            # 增加重试次数和调整重试延迟，提高交易执行成功率
            # 现货交易和现货杠杆交易都使用/trade/order端点
            endpoint = "/trade/order"
            
            logger.info(f"下单请求: {endpoint}, 参数: {body}")
            
            result = await self.request(
                "POST", endpoint, body=body,
                max_retries=5,  # 增加到5次重试
                retry_delay=2.0  # 增加重试延迟到2秒
            )
            
            if result:
                if isinstance(result, dict):
                    # 处理字典格式的响应
                    code = result.get("code")
                    data = result.get("data", [])
                    if code == "0" and data and len(data) > 0:
                        order_id = data[0].get("ordId")
                        if order_id:
                            logger.info(f"下单成功，订单ID: {order_id}")
                            return order_id
                        else:
                            logger.error(f"下单失败: 未返回订单ID, 响应: {result}")
                    else:
                        logger.error(f"下单失败: 响应格式错误, 响应: {result}")
                elif isinstance(result, list) and len(result) > 0:
                    # 处理列表格式的响应（兼容旧格式）
                    order_id = result[0].get("ordId")
                    if order_id:
                        logger.info(f"下单成功，订单ID: {order_id}")
                        return order_id
                    else:
                        logger.error(f"下单失败: 未返回订单ID, 响应: {result}")
                else:
                    logger.error(f"下单失败: 响应格式错误, 响应: {result}")
            else:
                logger.error("下单失败: API请求失败，返回None")
        except Exception as e:
            logger.error(f"下单异常: {e}")
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

    async def cancel_order_with_dict(self, order: Dict) -> Dict:
        """
        取消订单

        Args:
            order: 订单取消信息，包含ordId和instId等字段

        Returns:
            Dict: 取消订单结果
        """
        result = await self.request(
            "POST", "/trade/cancel-order", body=order
        )
        return result[0] if result else {}

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
            "POST", "/trade/cancel-batch-orders", body=orders
        )
        return result or []

    async def order(self, order: Dict) -> Dict:
        """
        下单

        Args:
            order: 订单信息，包含instId, side, ordType, sz等字段

        Returns:
            Dict: 下单结果
        """
        result = await self.request(
            "POST", "/trade/order", body=order
        )
        return result[0] if result else {}

    async def batch_orders(self, orders: List[Dict]) -> List[Dict]:
        """
        批量下单

        Args:
            orders: 订单列表，每个订单包含instId, side, ordType, sz等字段

        Returns:
            List[Dict]: 批量下单结果
        """
        result = await self.request(
            "POST", "/trade/batch-orders", body=orders
        )
        return result or []

    async def cancel_order_with_dict(self, order: Dict) -> Dict:
        """
        取消订单

        Args:
            order: 订单取消信息，包含ordId和instId等字段

        Returns:
            Dict: 取消订单结果
        """
        result = await self.request(
            "POST", "/trade/cancel-order", body=order
        )
        return result[0] if result else {}

    async def amend_order(self, order: Dict) -> Dict:
        """
        修改订单

        Args:
            order: 订单修改信息，包含ordId, newSz, instId等字段

        Returns:
            Dict: 修改订单结果
        """
        result = await self.request(
            "POST", "/trade/amend-order", body=order
        )
        return result[0] if result else {}

    async def amend_batch_orders(self, orders: List[Dict]) -> List[Dict]:
        """
        批量修改订单

        Args:
            orders: 订单修改列表，每个订单包含ordId, newSz, instId等字段

        Returns:
            List[Dict]: 批量修改订单结果
        """
        result = await self.request(
            "POST", "/trade/amend-batch-orders", body=orders
        )
        return result or []

    async def close_position(self, position: Dict) -> Dict:
        """
        平仓

        Args:
            position: 平仓信息，包含instId, mgnMode等字段

        Returns:
            Dict: 平仓结果
        """
        result = await self.request(
            "POST", "/trade/close-position", body=position
        )
        return result[0] if result else {}

    async def get_order(self, ord_id: str, inst_id: str) -> Dict:
        """
        获取订单信息

        Args:
            ord_id: 订单ID
            inst_id: 产品ID

        Returns:
            Dict: 订单信息
        """
        result = await self.request(
            "GET", "/trade/order", params={"ordId": ord_id, "instId": inst_id}
        )
        return result[0] if result else {}

    async def get_orders_pending(self, ord_type: str = "", inst_type: str = "") -> List[Dict]:
        """
        获取特定类型的挂单

        Args:
            ord_type: 订单类型，多个类型用逗号分隔，如 "post_only,fok,ioc"
            inst_type: 产品类型，如 "SPOT"

        Returns:
            List[Dict]: 挂单列表
        """
        params = {}
        if ord_type:
            params["ordType"] = ord_type
        if inst_type:
            params["instType"] = inst_type
        
        result = await self.request(
            "GET", "/trade/orders-pending", params=params
        )
        return result or []

    async def get_orders_history(self, ord_type: str = "", inst_type: str = "") -> List[Dict]:
        """
        获取特定类型的历史订单

        Args:
            ord_type: 订单类型，多个类型用逗号分隔，如 "post_only,fok,ioc"
            inst_type: 产品类型，如 "SPOT"

        Returns:
            List[Dict]: 历史订单列表
        """
        params = {}
        if ord_type:
            params["ordType"] = ord_type
        if inst_type:
            params["instType"] = inst_type
        
        result = await self.request(
            "GET", "/trade/orders-history", params=params
        )
        return result or []

    async def get_orders_history_archive(self, ord_type: str = "", inst_type: str = "") -> List[Dict]:
        """
        获取特定类型的历史订单归档

        Args:
            ord_type: 订单类型，多个类型用逗号分隔，如 "post_only,fok,ioc"
            inst_type: 产品类型，如 "SPOT"

        Returns:
            List[Dict]: 历史订单归档列表
        """
        params = {}
        if ord_type:
            params["ordType"] = ord_type
        if inst_type:
            params["instType"] = inst_type
        
        result = await self.request(
            "GET", "/trade/orders-history-archive", params=params
        )
        return result or []

    async def get_fills(self, inst_id: str = "", ord_id: str = "") -> List[Dict]:
        """
        获取成交明细

        Args:
            inst_id: 产品ID
            ord_id: 订单ID

        Returns:
            List[Dict]: 成交明细列表
        """
        params = {}
        if inst_id:
            params["instId"] = inst_id
        if ord_id:
            params["ordId"] = ord_id
        
        result = await self.request(
            "GET", "/trade/fills", params=params
        )
        return result or []

    async def get_fills_history(self, inst_type: str = "", inst_id: str = "") -> List[Dict]:
        """
        获取历史成交明细

        Args:
            inst_type: 产品类型，如 "SPOT"
            inst_id: 产品ID

        Returns:
            List[Dict]: 历史成交明细列表
        """
        params = {}
        if inst_type:
            params["instType"] = inst_type
        if inst_id:
            params["instId"] = inst_id
        
        result = await self.request(
            "GET", "/trade/fills-history", params=params
        )
        return result or []

    async def get_open_orders(self, inst_id: str = "") -> List[Dict]:
        """
        获取未成交订单

        Args:
            inst_id: 产品ID

        Returns:
            List[Dict]: 未成交订单列表
        """
        params = {}
        if inst_id:
            params["instId"] = inst_id

        result = await self.request("GET", "/trade/orders-pending", params=params)
        return result or []

    async def cancel_all_orders(self, inst_id: str) -> Dict:
        """
        取消所有订单

        Args:
            inst_id: 产品ID

        Returns:
            Dict: 取消结果
        """
        result = await self.request(
            "POST", "/trade/cancel-batch-orders", body={"instId": inst_id}
        )
        return result or {"code": "-1", "msg": "取消失败"}

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

    async def get_account_instruments(self, inst_type: str = "SPOT", inst_family: str = "", inst_id: str = "") -> List[Dict]:
        """
        获取当前账户可交易产品的信息列表

        Args:
            inst_type: 产品类型 (SPOT/MARGIN/SWAP/FUTURES/OPTION)
            inst_family: 交易品种，仅适用于交割/永续/期权，期权必填
            inst_id: 产品ID

        Returns:
            List[Dict]: 产品列表
        """
        params = {}
        if inst_type:
            params["instType"] = inst_type
        if inst_family:
            params["instFamily"] = inst_family
        if inst_id:
            params["instId"] = inst_id

        result = await self.request(
            "GET",
            "/account/instruments",
            params=params,
        )
        return result or []

    async def get_interest_accrued(self, ccy: str = "", after: str = "", before: str = "", limit: int = 100) -> List[Dict]:
        """
        获取计息记录

        Args:
            ccy: 币种
            after: 开始时间戳
            before: 结束时间戳
            limit: 数量限制

        Returns:
            List[Dict]: 计息记录列表
        """
        params = {}
        if ccy:
            params["ccy"] = ccy
        if after:
            params["after"] = after
        if before:
            params["before"] = before
        if limit:
            params["limit"] = str(limit)

        result = await self.request("GET", "/account/interest-accrued", params=params)
        return result or []

    async def get_interest_rate(self, ccy: str = "") -> List[Dict]:
        """
        获取用户当前市场借币利率

        Args:
            ccy: 币种

        Returns:
            List[Dict]: 借币利率列表
        """
        params = {}
        if ccy:
            params["ccy"] = ccy

        result = await self.request("GET", "/account/interest-rate", params=params)
        return result or []

    async def set_greeks(self, greeks_type: str) -> Dict:
        """
        期权greeks的PA/BS切换

        Args:
            greeks_type: greeks类型 (PA/BS)

        Returns:
            Dict: 设置结果
        """
        body = {
            "greeksType": greeks_type
        }

        result = await self.request("POST", "/account/set-greeks", body=body)
        return result[0] if result else {}

    async def set_isolated_mode(self, iso_mode: str, mode_type: str) -> Dict:
        """
        逐仓交易设置

        Args:
            iso_mode: 逐仓模式 (automatic)
            mode_type: 交易类型 (MARGIN)

        Returns:
            Dict: 设置结果
        """
        body = {
            "isoMode": iso_mode,
            "type": mode_type
        }

        result = await self.request("POST", "/account/set-isolated-mode", body=body)
        return result[0] if result else {}

    async def get_account_position_risk(self, inst_type: str = "", inst_id: str = "") -> List[Dict]:
        """
        查看账户持仓风险（仅适用于PM账户）

        Args:
            inst_type: 产品类型
            inst_id: 产品ID

        Returns:
            List[Dict]: 持仓风险列表
        """
        params = {}
        if inst_type:
            params["instType"] = inst_type
        if inst_id:
            params["instId"] = inst_id

        result = await self.request("GET", "/account/position-risk", params=params)
        return result or []

    async def get_interest_limits(self, ccy: str) -> List[Dict]:
        """
        获取借币利率与限额

        Args:
            ccy: 币种

        Returns:
            List[Dict]: 借币利率与限额列表
        """
        params = {
            "ccy": ccy
        }

        result = await self.request("GET", "/account/interest-limits", params=params)
        return result or []

    async def spot_manual_borrow_repay(self, ccy: str, side: str, amt: str) -> Dict:
        """
        现货手动借币/还币（仅适用于现货模式已开通借币的情况）

        Args:
            ccy: 币种
            side: 操作方向 (borrow/repay)
            amt: 金额

        Returns:
            Dict: 操作结果
        """
        body = {
            "ccy": ccy,
            "side": side,
            "amt": amt
        }

        result = await self.request("POST", "/account/spot-manual-borrow-repay", body=body)
        return result[0] if result else {}

    async def set_auto_repay(self, auto_repay: bool) -> Dict:
        """
        设置自动还币（仅适用于现货模式已开通借币的情况）

        Args:
            auto_repay: 是否开启自动还币 (true/false)

        Returns:
            Dict: 设置结果
        """
        body = {
            "autoRepay": str(auto_repay).lower()
        }

        result = await self.request("POST", "/account/set-auto-repay", body=body)
        return result[0] if result else {}

    async def spot_borrow_repay_history(self, ccy: str = "", type: str = "", after: str = "", before: str = "", limit: int = 100) -> List[Dict]:
        """
        获取现货模式下的借/还币历史

        Args:
            ccy: 币种
            type: 类型 (auto_borrow/auto_repay/manual_borrow/manual_repay)
            after: 开始时间戳
            before: 结束时间戳
            limit: 数量限制

        Returns:
            List[Dict]: 借/还币历史列表
        """
        params = {}
        if ccy:
            params["ccy"] = ccy
        if type:
            params["type"] = type
        if after:
            params["after"] = after
        if before:
            params["before"] = before
        if limit:
            params["limit"] = str(limit)

        result = await self.request("GET", "/account/spot-borrow-repay-history", params=params)
        return result or []

    async def position_builder(self, incl_real_pos_and_eq: bool, sim_pos: List[Dict]) -> Dict:
        """
        构建模拟持仓

        Args:
            incl_real_pos_and_eq: 是否包含真实持仓和权益
            sim_pos: 模拟持仓列表

        Returns:
            Dict: 构建结果
        """
        body = {
            "inclRealPosAndEq": str(incl_real_pos_and_eq).lower(),
            "simPos": sim_pos
        }

        result = await self.request("POST", "/account/position-builder", body=body)
        return result[0] if result else {}

    async def get_position_builder_graph(self, incl_real_pos_and_eq: bool, sim_pos: List[Dict]) -> Dict:
        """
        获取持仓构建器图表数据

        Args:
            incl_real_pos_and_eq: 是否包含真实持仓和权益
            sim_pos: 模拟持仓列表

        Returns:
            Dict: 图表数据
        """
        body = {
            "inclRealPosAndEq": str(incl_real_pos_and_eq).lower(),
            "simPos": sim_pos
        }

        result = await self.request("POST", "/account/position-builder-graph", body=body)
        return result[0] if result else {}

    async def set_risk_offset_amt(self, ccy: str, amt: str, type: str) -> Dict:
        """
        设置风险偏移量

        Args:
            ccy: 币种
            amt: 金额
            type: 类型 (add/reduce)

        Returns:
            Dict: 设置结果
        """
        body = {
            "ccy": ccy,
            "amt": amt,
            "type": type
        }

        result = await self.request("POST", "/account/set-riskOffset-amt", body=body)
        return result[0] if result else {}

    async def get_greeks(self, inst_type: str = "", inst_id: str = "") -> List[Dict]:
        """
        获取期权greeks信息

        Args:
            inst_type: 产品类型
            inst_id: 产品ID

        Returns:
            List[Dict]: greeks信息列表
        """
        params = {}
        if inst_type:
            params["instType"] = inst_type
        if inst_id:
            params["instId"] = inst_id

        result = await self.request("GET", "/account/greeks", params=params)
        return result or []

    async def get_position_tiers(self, inst_type: str, inst_id: str, td_mode: str) -> List[Dict]:
        """
        获取持仓档位信息

        Args:
            inst_type: 产品类型
            inst_id: 产品ID
            td_mode: 交易模式 (isolated/cross)

        Returns:
            List[Dict]: 持仓档位信息列表
        """
        params = {
            "instType": inst_type,
            "instId": inst_id,
            "tdMode": td_mode
        }

        result = await self.request("GET", "/account/position-tiers", params=params)
        return result or []

    async def activate_option(self) -> Dict:
        """
        激活期权功能

        Returns:
            Dict: 激活结果
        """
        result = await self.request("POST", "/account/activate-option")
        return result[0] if result else {}

    async def set_auto_loan(self, auto_loan: bool) -> Dict:
        """
        设置自动借币

        Args:
            auto_loan: 是否开启自动借币 (true/false)

        Returns:
            Dict: 设置结果
        """
        body = {
            "autoLoan": str(auto_loan).lower()
        }

        result = await self.request("POST", "/account/set-auto-loan", body=body)
        return result[0] if result else {}

    async def account_level_switch_preset(self, level: str) -> Dict:
        """
        账户等级切换预设

        Args:
            level: 账户等级

        Returns:
            Dict: 切换结果
        """
        body = {
            "level": level
        }

        result = await self.request("POST", "/account/account-level-switch-preset", body=body)
        return result[0] if result else {}

    async def set_account_level(self, level: str) -> Dict:
        """
        设置账户等级

        Args:
            level: 账户等级

        Returns:
            Dict: 设置结果
        """
        body = {
            "level": level
        }

        result = await self.request("POST", "/account/set-account-level", body=body)
        return result[0] if result else {}

    async def set_collateral_assets(self, collateral_assets: List[Dict]) -> Dict:
        """
        设置抵押资产

        Args:
            collateral_assets: 抵押资产列表

        Returns:
            Dict: 设置结果
        """
        body = {
            "collateralAssets": collateral_assets
        }

        result = await self.request("POST", "/account/set-collateral-assets", body=body)
        return result[0] if result else {}

    async def get_collateral_assets(self) -> List[Dict]:
        """
        获取抵押资产信息

        Returns:
            List[Dict]: 抵押资产列表
        """
        result = await self.request("GET", "/account/collateral-assets")
        return result or []

    async def mmp_reset(self) -> Dict:
        """
        重置MMP（Market Maker Protection）设置

        Returns:
            Dict: 重置结果
        """
        result = await self.request("POST", "/account/mmp-reset")
        return result[0] if result else {}

    async def mmp_config(self, mmp_config: Dict) -> Dict:
        """
        配置MMP（Market Maker Protection）设置

        Args:
            mmp_config: MMP配置信息

        Returns:
            Dict: 配置结果
        """
        body = mmp_config

        result = await self.request("POST", "/account/mmp-config", body=body)
        return result[0] if result else {}

    async def get_mmp_config(self) -> List[Dict]:
        """
        获取MMP（Market Maker Protection）配置信息

        Returns:
            List[Dict]: MMP配置信息列表
        """
        result = await self.request("GET", "/account/mmp-config")
        return result or []

    async def move_positions(self, move_positions: List[Dict]) -> Dict:
        """
        移动持仓

        Args:
            move_positions: 移动持仓列表

        Returns:
            Dict: 移动结果
        """
        body = {
            "movePositions": move_positions
        }

        result = await self.request("POST", "/account/move-positions", body=body)
        return result[0] if result else {}

    async def get_move_positions_history(self, after: str = "", before: str = "", limit: int = 100) -> List[Dict]:
        """
        获取移动持仓历史

        Args:
            after: 开始时间戳
            before: 结束时间戳
            limit: 数量限制

        Returns:
            List[Dict]: 移动持仓历史列表
        """
        params = {}
        if after:
            params["after"] = after
        if before:
            params["before"] = before
        if limit:
            params["limit"] = str(limit)

        result = await self.request("GET", "/account/move-positions-history", params=params)
        return result or []

    async def set_auto_earn(self, auto_earn: bool) -> Dict:
        """
        设置自动收益

        Args:
            auto_earn: 是否开启自动收益 (true/false)

        Returns:
            Dict: 设置结果
        """
        body = {
            "autoEarn": str(auto_earn).lower()
        }

        result = await self.request("POST", "/account/set-auto-earn", body=body)
        return result[0] if result else {}

    async def set_settle_currency(self, settle_currency: str) -> Dict:
        """
        设置结算货币

        Args:
            settle_currency: 结算货币

        Returns:
            Dict: 设置结果
        """
        body = {
            "settleCcy": settle_currency
        }

        result = await self.request("POST", "/account/set-settle-currency", body=body)
        return result[0] if result else {}

    async def set_trading_config(self, trading_config: Dict) -> Dict:
        """
        设置交易配置

        Args:
            trading_config: 交易配置信息

        Returns:
            Dict: 设置结果
        """
        body = trading_config

        result = await self.request("POST", "/account/set-trading-config", body=body)
        return result[0] if result else {}

    async def precheck_set_delta_neutral(self, inst_id: str, delta: str) -> Dict:
        """
        预检查设置delta中性

        Args:
            inst_id: 产品ID
            delta: delta值

        Returns:
            Dict: 预检查结果
        """
        params = {
            "instId": inst_id,
            "delta": delta
        }

        result = await self.request("GET", "/account/precheck-set-delta-neutral", params=params)
        return result[0] if result else {}

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
