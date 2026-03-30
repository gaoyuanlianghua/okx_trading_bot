"""
OKX WebSocket客户端 - 处理实时数据流
"""

import asyncio
import json
import logging
import time
from typing import Dict, Optional, Callable, List, Set
import websockets
from websockets.exceptions import ConnectionClosed

from .auth import OKXAuth
from .okx_rest_client import OKXRESTClient
from core.events.event_bus import Event, EventType, event_bus
from core.utils.logger import get_logger

logger = get_logger(__name__)


class OKXWebSocketClient:
    """
    OKX WebSocket客户端

    提供对OKX交易所WebSocket API的访问
    支持公共频道和私有频道
    """

    # WebSocket URL
    PUBLIC_URL = "wss://ws.okx.com:8443/ws/v5/public"
    PRIVATE_URL = "wss://ws.okx.com:8443/ws/v5/private"

    # 模拟盘URL
    PUBLIC_URL_TEST = "wss://wspap.okx.com:8443/ws/v5/public"
    PRIVATE_URL_TEST = "wss://wspap.okx.com:8443/ws/v5/private"

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        is_test: bool = False,
    ):
        """
        初始化WebSocket客户端

        Args:
            api_key: API密钥
            api_secret: API密钥密码
            passphrase: 密码短语
            is_test: 是否为模拟盘
        """
        self.auth = OKXAuth(api_key, api_secret, passphrase, is_test)
        self.is_test = is_test
        self.event_bus = event_bus

        # 创建REST客户端实例
        self.rest_client = OKXRESTClient(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            is_test=is_test,
        )

        # WebSocket连接
        self.public_ws: Optional[websockets.WebSocketClientProtocol] = None
        self.private_ws: Optional[websockets.WebSocketClientProtocol] = None

        # 连接状态
        self._public_connected = False
        self._private_connected = False
        self._logged_in = False

        # 订阅管理
        self._subscriptions: Set[str] = set()
        self._subscription_callbacks: Dict[str, List[Callable]] = {}

        # 任务管理
        self._tasks: List[asyncio.Task] = []
        self._running = False
        self._stop_event = asyncio.Event()

        # 重连配置
        self._max_reconnect_attempts = 10
        self._base_reconnect_delay = 5
        self._max_reconnect_delay = 60
        self._reconnect_attempts = {
            "public": 0,
            "private": 0
        }

        # 心跳配置
        self._heartbeat_interval = 20
        self._heartbeat_timeout = 60  # 心跳超时时间
        self._last_pong = time.time()

        # WebSocket消息记录
        self.ws_message_history = []
        self.max_history_size = 1000  # 最大历史记录数

        # 消息队列 - 用于异步处理消息
        self._message_queue = asyncio.Queue(maxsize=5000)  # 设置队列大小限制

        # 连接监控
        self._connection_monitor_task = None

        logger.info(f"WebSocket客户端初始化完成 (模拟盘: {is_test})")

    async def connect_public(self) -> bool:
        """
        连接公共WebSocket

        Returns:
            bool: 是否连接成功
        """
        url = self.PUBLIC_URL_TEST if self.is_test else self.PUBLIC_URL

        try:
            self.public_ws = await websockets.connect(url)
            self._public_connected = True

            # 启动消息接收任务
            task = asyncio.create_task(self._receive_public_messages())
            self._tasks.append(task)

            # 启动心跳任务
            task = asyncio.create_task(self._heartbeat_public())
            self._tasks.append(task)

            # 重新订阅
            await self._resubscribe_public()

            logger.info("公共WebSocket连接成功")

            # 发布连接事件
            await self.event_bus.publish_async(
                Event(
                    type=EventType.WS_CONNECTED,
                    source="websocket_client",
                    data={"channel": "public"},
                )
            )

            return True

        except Exception as e:
            logger.error(f"公共WebSocket连接失败: {e}")
            return False

    async def connect_private(self) -> bool:
        """
        连接私有WebSocket

        Returns:
            bool: 是否连接成功
        """
        url = self.PRIVATE_URL_TEST if self.is_test else self.PRIVATE_URL

        try:
            self.private_ws = await websockets.connect(url)
            self._private_connected = True

            # 登录
            if self.auth.is_configured():
                await self._login()

            # 启动消息接收任务
            task = asyncio.create_task(self._receive_private_messages())
            self._tasks.append(task)

            # 启动心跳任务
            task = asyncio.create_task(self._heartbeat_private())
            self._tasks.append(task)

            logger.info("私有WebSocket连接成功")

            # 发布连接事件
            await self.event_bus.publish_async(
                Event(
                    type=EventType.WS_CONNECTED,
                    source="websocket_client",
                    data={"channel": "private"},
                )
            )

            return True

        except Exception as e:
            logger.error(f"私有WebSocket连接失败: {e}")
            return False

    async def connect(self) -> bool:
        """
        连接所有WebSocket

        Returns:
            bool: 是否全部连接成功
        """
        self._running = True

        public_ok = await self.connect_public()
        private_ok = await self.connect_private()

        # 启动消息处理任务
        if public_ok or private_ok:
            task = asyncio.create_task(self._message_processor())
            self._tasks.append(task)

        # 启动连接监控任务
        task = asyncio.create_task(self._connection_monitor())
        self._tasks.append(task)

        return public_ok and private_ok

    async def _login(self):
        """登录私有频道"""
        if not self.private_ws or not self.auth.is_configured():
            return

        login_params = self.auth.get_websocket_login_params()
        await self.private_ws.send(json.dumps(login_params))
        logger.info("WebSocket登录请求已发送")

    async def subscribe(
        self, channel: str, inst_id: str = "", callback: Callable = None
    ) -> bool:
        """
        订阅频道

        Args:
            channel: 频道名称 (tickers/books/candles/trades等)
            inst_id: 产品ID
            callback: 回调函数

        Returns:
            bool: 是否订阅成功
        """
        subscription_key = f"{channel}:{inst_id}" if inst_id else channel

        # 构建订阅参数
        args = {"channel": channel}
        if inst_id:
            args["instId"] = inst_id

        subscribe_msg = {"op": "subscribe", "args": [args]}

        try:
            # 确定使用哪个连接
            is_private = channel in ["orders", "account", "positions"]
            ws = self.private_ws if is_private else self.public_ws

            if not ws:
                logger.error(f"WebSocket未连接，无法订阅: {subscription_key}")
                return False

            await ws.send(json.dumps(subscribe_msg))
            self._subscriptions.add(subscription_key)

            # 注册回调
            if callback:
                if subscription_key not in self._subscription_callbacks:
                    self._subscription_callbacks[subscription_key] = []
                self._subscription_callbacks[subscription_key].append(callback)

            logger.info(f"订阅成功: {subscription_key}")
            return True

        except Exception as e:
            logger.error(f"订阅失败 {subscription_key}: {e}")
            return False

    async def unsubscribe(self, channel: str, inst_id: str = "") -> bool:
        """
        取消订阅

        Args:
            channel: 频道名称
            inst_id: 产品ID

        Returns:
            bool: 是否取消成功
        """
        subscription_key = f"{channel}:{inst_id}" if inst_id else channel

        args = {"channel": channel}
        if inst_id:
            args["instId"] = inst_id

        unsubscribe_msg = {"op": "unsubscribe", "args": [args]}

        try:
            is_private = channel in ["orders", "account", "positions"]
            ws = self.private_ws if is_private else self.public_ws

            if ws:
                await ws.send(json.dumps(unsubscribe_msg))

            self._subscriptions.discard(subscription_key)
            self._subscription_callbacks.pop(subscription_key, None)

            logger.info(f"取消订阅: {subscription_key}")
            return True

        except Exception as e:
            logger.error(f"取消订阅失败 {subscription_key}: {e}")
            return False

    async def _resubscribe_public(self):
        """重新订阅公共频道"""
        for subscription in list(self._subscriptions):
            if ":" in subscription:
                channel, inst_id = subscription.split(":", 1)
                await self.subscribe(channel, inst_id)

    async def _receive_public_messages(self):
        """接收公共频道消息"""
        while self._running and self.public_ws:
            try:
                message = await self.public_ws.recv()
                # 将消息添加到队列
                await self._message_queue.put((message, "public"))
            except ConnectionClosed:
                logger.warning("公共WebSocket连接已关闭")
                self._public_connected = False
                await self._reconnect_public()
                break
            except Exception as e:
                logger.error(f"接收公共消息错误: {e}")

    async def _receive_private_messages(self):
        """接收私有频道消息"""
        while self._running and self.private_ws:
            try:
                message = await self.private_ws.recv()
                # 将消息添加到队列
                await self._message_queue.put((message, "private"))
            except ConnectionClosed:
                logger.warning("私有WebSocket连接已关闭")
                self._private_connected = False
                await self._reconnect_private()
                break
            except Exception as e:
                logger.error(f"接收私有消息错误: {e}")

    async def _handle_message(self, message: str, channel: str):
        """
        处理收到的消息

        Args:
            message: 消息内容
            channel: 频道类型 (public/private)
        """
        import time

        start_time = time.time()

        # 准备消息记录
        message_record = {
            "timestamp": time.time(),
            "channel": channel,
            "message": message,
            "message_type": "unknown",
            "channel_name": None,
            "inst_id": None,
            "process_time": None,
            "error": None,
        }

        try:
            data = json.loads(message)
            message_record["message_type"] = "json"

            # 处理事件消息
            if "event" in data:
                event_type = data.get("event")
                message_record["message_type"] = "event"
                message_record["channel_name"] = event_type
                logger.debug(f"收到事件消息 [{channel}]: {event_type}")
                await self._handle_event(data, channel)
                return

            # 处理数据推送
            if "arg" in data and "data" in data:
                arg = data.get("arg", {})
                channel_name = arg.get("channel", "")
                inst_id = arg.get("instId", "")
                message_record["message_type"] = "data_push"
                message_record["channel_name"] = channel_name
                message_record["inst_id"] = inst_id
                logger.debug(f"收到数据推送 [{channel}]: {channel_name} {inst_id}")
                await self._handle_data_push(data, channel)
                return

            # 处理pong响应
            if data == "pong":
                self._last_pong = time.time()
                message_record["message_type"] = "pong"
                logger.debug(f"收到pong响应 [{channel}]")
                return

            logger.debug(f"收到消息 [{channel}]: {message}")

        except json.JSONDecodeError:
            # 处理ping消息
            if message == "ping":
                message_record["message_type"] = "ping"
                logger.debug(f"收到ping消息 [{channel}]")
                return
            error_msg = f"无法解析消息: {message}"
            logger.warning(error_msg)
            message_record["error"] = error_msg
        except Exception as e:
            error_msg = f"处理消息错误: {e}"
            logger.error(error_msg)
            message_record["error"] = error_msg
        finally:
            process_time = time.time() - start_time
            message_record["process_time"] = process_time

            # 添加到消息历史
            self.ws_message_history.append(message_record)
            # 限制历史记录长度
            if len(self.ws_message_history) > self.max_history_size:
                self.ws_message_history = self.ws_message_history[
                    -self.max_history_size :
                ]

            if process_time > 0.1:
                logger.warning(f"消息处理耗时过长: {process_time:.3f}s")

    async def _handle_event(self, data: Dict, channel: str):
        """处理事件消息"""
        event = data.get("event")

        if event == "login":
            if data.get("code") == "0":
                self._logged_in = True
                logger.info("WebSocket登录成功")
            else:
                logger.error(f"WebSocket登录失败: {data.get('msg')}")

        elif event == "subscribe":
            logger.debug(f"订阅确认: {data.get('arg')}")

        elif event == "unsubscribe":
            logger.debug(f"取消订阅确认: {data.get('arg')}")

        elif event == "error":
            logger.error(f"WebSocket错误: {data.get('msg')}")
            await self.event_bus.publish_async(
                Event(
                    type=EventType.WS_ERROR,
                    source="websocket_client",
                    data={"error": data.get("msg"), "channel": channel},
                )
            )

    async def _handle_data_push(self, data: Dict, channel: str):
        """处理数据推送"""
        arg = data.get("arg", {})
        channel_name = arg.get("channel", "")
        inst_id = arg.get("instId", "")

        subscription_key = f"{channel_name}:{inst_id}" if inst_id else channel_name

        # 发布到事件总线
        event_type = self._get_event_type(channel_name)
        await self.event_bus.publish_async(
            Event(
                type=event_type,
                source="websocket_client",
                data={
                    "channel": channel_name,
                    "inst_id": inst_id,
                    "data": data.get("data", []),
                },
            )
        )

        # 调用注册的回调
        callbacks = self._subscription_callbacks.get(subscription_key, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"回调执行错误: {e}")

    def _get_event_type(self, channel: str) -> EventType:
        """根据频道名称获取事件类型"""
        channel_event_map = {
            "tickers": EventType.MARKET_DATA_TICKER,
            "books": EventType.MARKET_DATA_ORDERBOOK,
            "candle": EventType.MARKET_DATA_KLINE,
            "trades": EventType.MARKET_DATA_TRADE,
            "orders": EventType.ORDER_UPDATED,
            "account": EventType.CUSTOM,
            "positions": EventType.CUSTOM,
        }
        return channel_event_map.get(channel, EventType.CUSTOM)

    async def _heartbeat_public(self):
        """公共频道心跳"""
        while self._running and self.public_ws:
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self._heartbeat_interval
                )
            except asyncio.TimeoutError:
                if self.public_ws and self._public_connected:
                    try:
                        await self.public_ws.send("ping")
                    except Exception as e:
                        logger.error(f"发送心跳失败: {e}")

    async def _heartbeat_private(self):
        """私有频道心跳"""
        while self._running and self.private_ws:
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self._heartbeat_interval
                )
            except asyncio.TimeoutError:
                if self.private_ws and self._private_connected:
                    try:
                        await self.private_ws.send("ping")
                    except Exception as e:
                        logger.error(f"发送心跳失败: {e}")



    async def _reconnect_public(self):
        """重新连接公共频道"""
        self._reconnect_attempts["public"] += 1
        
        # 指数退避策略
        delay = min(self._base_reconnect_delay * (2 ** (self._reconnect_attempts["public"] - 1)), self._max_reconnect_delay)
        
        logger.info(
            f"尝试重新连接公共WebSocket ({self._reconnect_attempts['public']}/{self._max_reconnect_attempts})，延迟 {delay:.2f}秒"
        )

        await asyncio.sleep(delay)

        if await self.connect_public():
            self._reconnect_attempts["public"] = 0
            return

        if self._reconnect_attempts["public"] >= self._max_reconnect_attempts:
            logger.error("公共WebSocket重连失败")
            await self.event_bus.publish_async(
                Event(
                    type=EventType.WS_DISCONNECTED,
                    source="websocket_client",
                    data={"channel": "public", "reconnect_failed": True},
                )
            )
            # 重置重连尝试次数
            self._reconnect_attempts["public"] = 0

    async def _reconnect_private(self):
        """重新连接私有频道"""
        self._reconnect_attempts["private"] += 1
        
        # 指数退避策略
        delay = min(self._base_reconnect_delay * (2 ** (self._reconnect_attempts["private"] - 1)), self._max_reconnect_delay)
        
        logger.info(
            f"尝试重新连接私有WebSocket ({self._reconnect_attempts['private']}/{self._max_reconnect_attempts})，延迟 {delay:.2f}秒"
        )

        await asyncio.sleep(delay)

        if await self.connect_private():
            self._reconnect_attempts["private"] = 0
            return

        if self._reconnect_attempts["private"] >= self._max_reconnect_attempts:
            logger.error("私有WebSocket重连失败")
            await self.event_bus.publish_async(
                Event(
                    type=EventType.WS_DISCONNECTED,
                    source="websocket_client",
                    data={"channel": "private", "reconnect_failed": True},
                )
            )
            # 重置重连尝试次数
            self._reconnect_attempts["private"] = 0

    async def _connection_monitor(self):
        """连接监控任务，检测连接状态和心跳超时"""
        while self._running:
            try:
                await asyncio.sleep(10)  # 每10秒检查一次
                
                # 检查心跳超时
                current_time = time.time()
                if current_time - self._last_pong > self._heartbeat_timeout:
                    logger.warning(f"心跳超时，最后一次pong时间: {self._last_pong}")
                    
                    # 重新连接公共和私有WebSocket
                    if self._public_connected:
                        logger.warning("公共WebSocket心跳超时，尝试重新连接")
                        asyncio.create_task(self._reconnect_public())
                    if self._private_connected:
                        logger.warning("私有WebSocket心跳超时，尝试重新连接")
                        asyncio.create_task(self._reconnect_private())
                
                # 检查连接状态
                if self._running:
                    if not self._public_connected:
                        logger.warning("公共WebSocket连接已断开，尝试重新连接")
                        asyncio.create_task(self._reconnect_public())
                    if not self._private_connected and self.auth.is_configured():
                        logger.warning("私有WebSocket连接已断开，尝试重新连接")
                        asyncio.create_task(self._reconnect_private())
                        
            except Exception as e:
                logger.error(f"连接监控错误: {e}")
                await asyncio.sleep(5)

    async def close(self):
        """关闭连接"""
        self._running = False
        self._stop_event.set()

        # 取消所有任务
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._tasks.clear()

        # 关闭连接
        if self.public_ws:
            await self.public_ws.close()
        if self.private_ws:
            await self.private_ws.close()

        # 关闭REST客户端
        await self.rest_client.close()

        logger.info("WebSocket客户端已关闭")

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._public_connected and self._private_connected

    async def _message_processor(self):
        """消息处理器 - 从队列中获取消息并处理"""
        while self._running:
            try:
                # 从队列中获取消息，设置超时以便能够响应停止事件
                try:
                    message, channel = await asyncio.wait_for(
                        self._message_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # 超时，检查是否需要停止
                    continue

                # 处理消息
                await self._handle_message(message, channel)

                # 标记任务完成
                self._message_queue.task_done()

            except asyncio.CancelledError:
                # 任务被取消
                break
            except Exception as e:
                logger.error(f"消息处理器错误: {e}")

    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        return self._logged_in
