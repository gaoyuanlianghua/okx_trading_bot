"""
订单智能体 - 负责订单管理
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_agent import BaseAgent, AgentConfig
from core.events.event_bus import Event, EventType
from core.events.agent_communication import Message, MessageType
from core.api.exchange_manager import exchange_manager
from core.utils.logger import get_logger

logger = get_logger(__name__)


class OrderAgent(BaseAgent):
    """
    订单智能体

    职责：
    1. 下单、撤单
    2. 查询订单状态
    3. 管理未成交订单
    4. 处理订单事件
    """

    def __init__(self, config: AgentConfig, exchange_name: str = "okx", **exchange_kwargs):
        super().__init__(config)
        self.exchange_name = exchange_name
        self.rest_client = exchange_manager.get_exchange(exchange_name, **exchange_kwargs)

        # 订单缓存
        self._orders_cache: Dict[str, Dict] = {}
        self._pending_orders: Dict[str, Dict] = {}

        # 交易记录
        self._trade_history: List[Dict] = []

        # 收益跟踪
        self._total_pnl = 0.0
        self._total_fees = 0.0

        # 统计
        self._order_count = 0
        self._filled_count = 0
        self._cancelled_count = 0

        logger.info(f"订单智能体初始化完成: {self.agent_id}")

    async def _initialize(self):
        """初始化"""
        self.register_message_handler(
            MessageType.COMMAND_START, self._handle_order_command
        )

        # 订阅订单事件
        self.event_bus.subscribe(
            EventType.ORDER_CREATED, self._on_order_event, async_callback=True
        )
        self.event_bus.subscribe(
            EventType.ORDER_UPDATED, self._on_order_event, async_callback=True
        )
        self.event_bus.subscribe(
            EventType.ORDER_FILLED, self._on_order_event, async_callback=True
        )
        self.event_bus.subscribe(
            EventType.ORDER_CANCELLED, self._on_order_event, async_callback=True
        )

        logger.info("订单智能体初始化完成")

    async def _cleanup(self):
        """清理"""
        self._orders_cache.clear()
        self._pending_orders.clear()
        logger.info("订单智能体已清理")

    async def _execute_cycle(self):
        """执行周期"""
        # 定期同步订单状态
        await self._sync_orders()
        await asyncio.sleep(10)

    async def _sync_orders(self):
        """同步订单状态"""
        if not self.rest_client:
            return

        try:
            # 获取未成交订单
            pending = await self.rest_client.get_pending_orders()
            self._pending_orders = {order.get("ordId"): order for order in pending}

            # 更新缓存
            for order in pending:
                self._orders_cache[order.get("ordId")] = order

        except Exception as e:
            logger.error(f"同步订单失败: {e}")

    async def _handle_order_command(self, message: Message):
        """处理订单命令"""
        payload = message.payload
        action = payload.get("action")

        if action == "place":
            result = await self.place_order(payload)
        elif action == "cancel":
            result = await self.cancel_order(payload)
        elif action == "query":
            result = await self.query_order(payload)
        else:
            result = {"success": False, "error": "未知命令"}

        # 发送响应
        response = Message.create_response(
            sender=self.agent_id,
            receiver=message.sender,
            request_message=message,
            payload=result,
        )
        await self.send_message(response)

    async def _on_order_event(self, event: Event):
        """处理订单事件"""
        order_data = event.data.get("order", {})
        order_id = order_data.get("ordId")

        if order_id:
            self._orders_cache[order_id] = order_data
            self.metrics.update_activity()

            # 更新统计
            state = order_data.get("state")
            if state == "filled":
                self._filled_count += 1
                self._pending_orders.pop(order_id, None)

                # 记录交易
                trade = self._create_trade_record(order_data)
                if trade:
                    self._trade_history.append(trade)
                    # 计算收益
                    self._calculate_pnl(trade)
            elif state == "canceled":
                self._cancelled_count += 1
                self._pending_orders.pop(order_id, None)

    def _create_trade_record(self, order_data: Dict) -> Dict:
        """创建交易记录"""
        try:
            trade = {
                "trade_id": order_data.get("ordId"),
                "inst_id": order_data.get("instId"),
                "side": order_data.get("side"),
                "ord_type": order_data.get("ordType"),
                "price": float(order_data.get("avgPx", 0)),
                "size": float(order_data.get("sz", 0)),
                "filled_size": float(order_data.get("accFillSz", 0)),
                "fee": float(order_data.get("fee", 0)),
                "state": order_data.get("state"),
                "timestamp": order_data.get("cTime"),
                "fill_time": order_data.get("fillTime"),
            }
            return trade
        except Exception as e:
            logger.error(f"创建交易记录失败: {e}")
            return {}

    def _calculate_pnl(self, trade: Dict):
        """计算交易收益"""
        try:
            # 简化的PnL计算
            # 实际应用中需要根据当前价格和持仓情况计算
            # 这里仅记录交易信息，实际PnL计算需要更复杂的逻辑
            self._total_fees += trade.get("fee", 0)

        except Exception as e:
            logger.error(f"计算收益失败: {e}")

    # ========== 公共接口 ==========

    async def place_order(self, params: Dict) -> Dict:
        """
        下单

        Args:
            params: 订单参数

        Returns:
            Dict: 下单结果
        """
        if not self.rest_client:
            return {"success": False, "error": "REST客户端未初始化"}

        try:
            order_id = await self.rest_client.place_order(
                inst_id=params.get("inst_id", "BTC-USDT-SWAP"),
                side=params.get("side", "buy"),
                ord_type=params.get("ord_type", "limit"),
                sz=str(params.get("sz", "0")),
                px=str(params.get("px", "")),
                td_mode=params.get("td_mode", "cross"),
            )

            if order_id:
                self._order_count += 1
                logger.info(f"下单成功: {order_id}")
                return {"success": True, "order_id": order_id}
            else:
                return {"success": False, "error": "下单失败"}

        except Exception as e:
            logger.error(f"下单失败: {e}")
            return {"success": False, "error": str(e)}

    async def cancel_order(self, params: Dict) -> Dict:
        """
        撤单

        Args:
            params: 撤单参数

        Returns:
            Dict: 撤单结果
        """
        if not self.rest_client:
            return {"success": False, "error": "REST客户端未初始化"}

        try:
            success = await self.rest_client.cancel_order(
                inst_id=params.get("inst_id", "BTC-USDT-SWAP"),
                ord_id=params.get("order_id", ""),
                cl_ord_id=params.get("cl_ord_id", ""),
            )

            if success:
                logger.info(f"撤单成功: {params.get('order_id')}")
                return {"success": True}
            else:
                return {"success": False, "error": "撤单失败"}

        except Exception as e:
            logger.error(f"撤单失败: {e}")
            return {"success": False, "error": str(e)}

    async def query_order(self, params: Dict) -> Dict:
        """
        查询订单

        Args:
            params: 查询参数

        Returns:
            Dict: 订单信息
        """
        order_id = params.get("order_id")

        # 先从缓存查询
        if order_id in self._orders_cache:
            return {"success": True, "order": self._orders_cache[order_id]}

        # 从API查询
        if self.rest_client:
            try:
                order = await self.rest_client.get_order_info(
                    inst_id=params.get("inst_id", "BTC-USDT-SWAP"), ord_id=order_id
                )
                if order:
                    return {"success": True, "order": order}
            except Exception as e:
                logger.error(f"查询订单失败: {e}")

        return {"success": False, "error": "订单不存在"}

    def get_pending_orders(self) -> List[Dict]:
        """获取未成交订单"""
        return list(self._pending_orders.values())

    def get_trade_history(self, limit: int = 100) -> List[Dict]:
        """获取交易历史"""
        return self._trade_history[-limit:]

    def get_pnl(self) -> Dict[str, float]:
        """获取收益信息"""
        return {"total_pnl": self._total_pnl, "total_fees": self._total_fees}

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        base_status = super().get_status()
        base_status.update(
            {
                "order_count": self._order_count,
                "filled_count": self._filled_count,
                "cancelled_count": self._cancelled_count,
                "pending_count": len(self._pending_orders),
                "trade_count": len(self._trade_history),
                "total_pnl": self._total_pnl,
                "total_fees": self._total_fees,
            }
        )
        return base_status
