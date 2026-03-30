"""
风险管理智能体 - 负责风险控制
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List

from .base_agent import BaseAgent, AgentConfig
from core.events.event_bus import Event, EventType
from core.events.agent_communication import Message, MessageType
from core.api.okx_rest_client import OKXRESTClient

logger = logging.getLogger(__name__)


class RiskAgent(BaseAgent):
    """
    风险管理智能体

    职责：
    1. 监控账户风险
    2. 检查订单风险
    3. 管理仓位限制
    4. 触发风险警报
    """

    def __init__(
        self,
        config: AgentConfig,
        rest_client: OKXRESTClient = None,
        strategy_agent=None,
    ):
        super().__init__(config)
        self.rest_client = rest_client
        self.strategy_agent = strategy_agent

        # 风险参数
        self._risk_params = {
            "max_position_ratio": 0.8,  # 最大仓位比例
            "max_daily_loss": 0.05,  # 最大日亏损
            "max_order_amount": 10000,  # 最大订单金额
            "max_leverage": 10,  # 最大杠杆
            "stop_loss_ratio": 0.03,  # 止损比例
            "take_profit_ratio": 0.05,  # 止盈比例
        }

        # 风险状态
        self._account_balance = 0
        self._positions = []
        self._daily_pnl = 0
        self._risk_level = "low"  # low/medium/high/critical

        # 账户信息
        self._account_info = {
            "total_balance": 0.0,
            "available_balance": 0.0,
            "margin": 0.0,
            "unrealized_pnl": 0.0,
        }

        # 资产分布
        self._asset_distribution = {}

        # 警报状态
        self._alerts = []

        # 策略性能指标
        self._strategy_metrics = {}

        # 预警阈值配置
        self._alert_thresholds = {
            "max_drawdown": 0.2,  # 最大回撤 20%
            "sharpe_ratio": 1.0,  # 夏普比率低于 1.0
            "win_rate": 0.4,  # 胜率低于 40%
            "consecutive_losses": 5,  # 连续亏损次数
            "daily_loss": 0.05,  # 日亏损 5%
        }

        # 预警历史
        self._alert_history = []

        logger.info(f"风险管理智能体初始化完成: {self.agent_id}")

    async def _initialize(self):
        """初始化"""
        self.register_message_handler(MessageType.REQUEST_DATA, self._handle_risk_check)
        self.register_message_handler(
            MessageType.STRATEGY_METRICS, self._handle_strategy_metrics
        )

        # 订阅相关事件
        self.event_bus.subscribe(
            EventType.ORDER_CREATED, self._on_order_event, async_callback=True
        )
        self.event_bus.subscribe(
            EventType.RISK_ALERT, self._on_risk_alert, async_callback=True
        )
        self.event_bus.subscribe(
            EventType.STRATEGY_PERFORMANCE,
            self._on_strategy_performance,
            async_callback=True,
        )

        logger.info("风险管理智能体初始化完成")

    async def _cleanup(self):
        """清理"""
        self._alerts.clear()
        self._strategy_metrics.clear()
        self._alert_history.clear()
        logger.info("风险管理智能体已清理")

    async def _execute_cycle(self):
        """执行周期"""
        await self._update_account_info()
        await self._assess_risk()
        await self._check_strategy_risks()
        await asyncio.sleep(30)

    async def _update_account_info(self):
        """更新账户信息"""
        if not self.rest_client:
            return

        try:
            # 获取账户余额
            balance = await self.rest_client.get_account_balance()
            if balance:
                self._account_balance = float(balance.get("totalEq", 0))

                # 提取账户信息
                self._account_info = {
                    "total_balance": float(balance.get("totalEq", 0)),
                    "available_balance": float(balance.get("availBal", 0)),
                    "margin": float(balance.get("margin", 0)),
                    "unrealized_pnl": float(balance.get("upl", 0)),
                }

                # 构建资产分布
                self._asset_distribution = {}
                if "details" in balance:
                    for detail in balance["details"]:
                        ccy = detail.get("ccy")
                        if ccy:
                            self._asset_distribution[ccy] = {
                                "balance": float(detail.get("bal", 0)),
                                "available": float(detail.get("availBal", 0)),
                            }

            # 获取持仓
            positions = await self.rest_client.get_positions()
            self._positions = positions

        except Exception as e:
            logger.error(f"更新账户信息失败: {e}")

    async def _assess_risk(self):
        """评估风险"""
        # 计算仓位比例
        position_value = sum(
            float(pos.get("pos", 0)) * float(pos.get("avgPx", 0))
            for pos in self._positions
        )

        position_ratio = (
            position_value / self._account_balance if self._account_balance > 0 else 0
        )

        # 确定风险等级
        if position_ratio > self._risk_params["max_position_ratio"]:
            self._risk_level = "critical"
            await self._trigger_alert("仓位过高", position_ratio)
        elif position_ratio > 0.6:
            self._risk_level = "high"
        elif position_ratio > 0.3:
            self._risk_level = "medium"
        else:
            self._risk_level = "low"

    async def _trigger_alert(
        self, reason: str, value: float, alert_type: str = "account"
    ):
        """触发警报"""
        alert = {
            "timestamp": asyncio.get_event_loop().time(),
            "reason": reason,
            "value": value,
            "level": self._risk_level,
            "type": alert_type,
        }
        self._alerts.append(alert)
        self._alert_history.append(alert)

        # 限制预警历史长度
        if len(self._alert_history) > 100:
            self._alert_history = self._alert_history[-100:]

        logger.warning(f"风险警报: {reason} = {value}")

        # 发布风险预警事件
        await self.event_bus.publish_async(
            Event(type=EventType.RISK_ALERT, source=self.agent_id, data=alert)
        )

    async def _check_strategy_risks(self):
        """检查策略风险"""
        for strategy_name, metrics in self._strategy_metrics.items():
            # 检查最大回撤
            max_drawdown = metrics.get("max_drawdown", 0)
            if max_drawdown > self._alert_thresholds["max_drawdown"]:
                await self._trigger_alert(
                    f"策略 {strategy_name} 最大回撤超过阈值", max_drawdown, "strategy"
                )
                # 执行自动风控
                await self._auto_risk_control(
                    strategy_name, "max_drawdown", max_drawdown
                )

            # 检查夏普比率
            sharpe_ratio = metrics.get("sharpe_ratio", 0)
            if sharpe_ratio < self._alert_thresholds["sharpe_ratio"]:
                await self._trigger_alert(
                    f"策略 {strategy_name} 夏普比率低于阈值", sharpe_ratio, "strategy"
                )

            # 检查胜率
            win_rate = metrics.get("win_rate", 0)
            if win_rate < self._alert_thresholds["win_rate"]:
                await self._trigger_alert(
                    f"策略 {strategy_name} 胜率低于阈值", win_rate, "strategy"
                )

            # 检查连续亏损次数
            consecutive_losses = metrics.get("consecutive_losses", 0)
            if consecutive_losses >= self._alert_thresholds["consecutive_losses"]:
                await self._trigger_alert(
                    f"策略 {strategy_name} 连续亏损次数超过阈值",
                    consecutive_losses,
                    "strategy",
                )
                # 执行自动风控
                await self._auto_risk_control(
                    strategy_name, "consecutive_losses", consecutive_losses
                )

            # 检查日亏损
            daily_loss = metrics.get("daily_loss", 0)
            if daily_loss > self._alert_thresholds["daily_loss"]:
                await self._trigger_alert(
                    f"策略 {strategy_name} 日亏损超过阈值", daily_loss, "strategy"
                )
                # 执行自动风控
                await self._auto_risk_control(strategy_name, "daily_loss", daily_loss)

    async def _auto_risk_control(
        self, strategy_name: str, risk_type: str, risk_value: float
    ):
        """自动风控"""
        logger.warning(
            f"执行自动风控: 策略={strategy_name}, 风险类型={risk_type}, 风险值={risk_value}"
        )

        # 根据风险类型执行不同的风控措施
        if risk_type == "max_drawdown" and risk_value > 0.3:  # 最大回撤超过30%
            # 停止策略
            await self._stop_strategy(strategy_name)
        elif risk_type == "consecutive_losses" and risk_value >= 10:  # 连续亏损10次
            # 停止策略
            await self._stop_strategy(strategy_name)
        elif risk_type == "daily_loss" and risk_value > 0.1:  # 日亏损超过10%
            # 停止策略
            await self._stop_strategy(strategy_name)
        elif risk_type == "daily_loss" and risk_value > 0.05:  # 日亏损超过5%
            # 调整仓位
            await self._adjust_position(strategy_name, 0.5)  # 减半仓位

    async def _stop_strategy(self, strategy_name: str):
        """停止策略"""
        if self.strategy_agent:
            try:
                result = await self.strategy_agent.deactivate_strategy(strategy_name)
                if result.get("success"):
                    logger.info(f"自动停止策略: {strategy_name}")
                else:
                    logger.error(
                        f"自动停止策略失败: {strategy_name}, 原因: {result.get('error')}"
                    )
            except Exception as e:
                logger.error(f"停止策略时出错: {e}")
        else:
            logger.error("策略智能体未初始化，无法停止策略")

    async def _adjust_position(self, strategy_name: str, adjustment_factor: float):
        """调整仓位"""
        logger.info(f"调整策略仓位: {strategy_name}, 调整因子: {adjustment_factor}")

        # 这里可以实现具体的仓位调整逻辑
        # 例如，通过API调整策略的仓位参数
        # 或者通过消息通知策略智能体调整仓位

        # 发布仓位调整事件
        await self.event_bus.publish_async(
            Event(
                type=EventType.POSITION_ADJUSTMENT,
                source=self.agent_id,
                data={
                    "strategy_name": strategy_name,
                    "adjustment_factor": adjustment_factor,
                    "reason": "风险控制",
                },
            )
        )

    async def _handle_risk_check(self, message: Message):
        """处理风险检查请求"""
        payload = message.payload
        check_type = payload.get("check_type")

        if check_type == "order":
            result = await self.check_order_risk(payload.get("order", {}))
        elif check_type == "account":
            result = await self.check_account_risk()
        else:
            result = {"allowed": False, "reason": "未知检查类型"}

        response = Message.create_response(
            sender=self.agent_id,
            receiver=message.sender,
            request_message=message,
            payload=result,
        )
        await self.send_message(response)

    async def _on_order_event(self, event: Event):
        """处理订单事件"""
        self.metrics.update_activity()

    async def _on_risk_alert(self, event: Event):
        """处理风险警报事件"""
        logger.warning(f"收到风险警报: {event.data}")

    async def _handle_strategy_metrics(self, message: Message):
        """处理策略性能指标消息"""
        payload = message.payload
        strategy_name = payload.get("strategy_name")
        metrics = payload.get("metrics")

        if strategy_name and metrics:
            self._strategy_metrics[strategy_name] = metrics
            logger.info(f"更新策略性能指标: {strategy_name}")

        response = Message.create_response(
            sender=self.agent_id,
            receiver=message.sender,
            request_message=message,
            payload={"success": True},
        )
        await self.send_message(response)

    async def _on_strategy_performance(self, event: Event):
        """处理策略性能事件"""
        data = event.data
        strategy_name = data.get("strategy_name")
        metrics = data.get("metrics")

        if strategy_name and metrics:
            self._strategy_metrics[strategy_name] = metrics
            logger.info(f"收到策略性能事件: {strategy_name}")
            # 立即检查风险
            await self._check_strategy_risks()

    # ========== 公共接口 ==========

    async def check_order_risk(self, order: Dict) -> Dict:
        """
        检查订单风险

        Args:
            order: 订单信息

        Returns:
            Dict: 检查结果
        """
        # 检查订单金额
        amount = float(order.get("sz", 0)) * float(order.get("px", 0))
        if amount > self._risk_params["max_order_amount"]:
            return {"allowed": False, "reason": f"订单金额超过限制: {amount}"}

        # 检查风险等级
        if self._risk_level == "critical":
            return {"allowed": False, "reason": "当前风险等级为critical，禁止新订单"}

        return {"allowed": True}

    async def check_account_risk(self) -> Dict:
        """
        检查账户风险

        Returns:
            Dict: 检查结果
        """
        return {
            "allowed": self._risk_level != "critical",
            "risk_level": self._risk_level,
            "account_balance": self._account_balance,
            "position_count": len(self._positions),
        }

    def get_risk_params(self) -> Dict:
        """获取风险参数"""
        return self._risk_params.copy()

    def set_risk_params(self, params: Dict):
        """设置风险参数"""
        self._risk_params.update(params)

    def get_account_info(self) -> Dict[str, float]:
        """获取账户信息"""
        return self._account_info.copy()

    def get_asset_distribution(self) -> Dict[str, Dict]:
        """获取资产分布"""
        return self._asset_distribution.copy()

    def get_strategy_metrics(self) -> Dict[str, Dict]:
        """获取策略性能指标"""
        return self._strategy_metrics.copy()

    def get_alert_thresholds(self) -> Dict[str, float]:
        """获取预警阈值"""
        return self._alert_thresholds.copy()

    def set_alert_thresholds(self, thresholds: Dict[str, float]):
        """设置预警阈值"""
        self._alert_thresholds.update(thresholds)

    def get_alerts(self) -> List[Dict]:
        """获取当前警报"""
        return self._alerts.copy()

    def get_alert_history(self) -> List[Dict]:
        """获取预警历史"""
        return self._alert_history.copy()

    def clear_alerts(self):
        """清空当前警报"""
        self._alerts.clear()

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        base_status = super().get_status()
        base_status.update(
            {
                "risk_level": self._risk_level,
                "account_balance": self._account_balance,
                "position_count": len(self._positions),
                "alert_count": len(self._alerts),
                "strategy_count": len(self._strategy_metrics),
                "account_info": self._account_info,
                "asset_distribution": self._asset_distribution,
                "alert_thresholds": self._alert_thresholds,
            }
        )
        return base_status
