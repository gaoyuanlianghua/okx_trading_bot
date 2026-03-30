"""
策略智能体 - 负责策略执行
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
import sys
import os

# 添加策略目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from .base_agent import BaseAgent, AgentConfig
from core.events.event_bus import Event, EventType
from core.events.agent_communication import Message, MessageType, MessageTemplates

from core.utils.logger import get_logger

logger = get_logger(__name__)


class StrategyAgent(BaseAgent):
    """
    策略智能体

    职责：
    1. 加载和管理策略
    2. 执行策略信号生成
    3. 协调策略与订单执行
    """

    def __init__(self, config: AgentConfig, market_data_agent=None, order_agent=None, exchange_name: str = "okx"):
        super().__init__(config)

        # 交易所配置
        self.exchange_name = exchange_name
        
        # 依赖的智能体
        self.market_data_agent = market_data_agent
        self.order_agent = order_agent

        # 策略管理
        self._strategies: Dict[str, BaseStrategy] = {}
        self._active_strategies: List[str] = []  # 支持多个策略同时运行

        # 信号缓存
        self._signals: List[Dict] = []

        # 默认策略配置
        self._default_inst_id = "BTC-USDT-SWAP"

        logger.info(f"策略智能体初始化完成: {self.agent_id}")

    async def _initialize(self):
        """初始化"""
        self.register_message_handler(
            MessageType.COMMAND_START, self._handle_strategy_command
        )

        # 订阅市场数据事件
        self.event_bus.subscribe(
            EventType.MARKET_DATA_TICKER, self._on_market_data, async_callback=True
        )

        # 加载默认策略
        await self._load_default_strategies()

        logger.info("策略智能体初始化完成")

    async def _cleanup(self):
        """清理"""
        # 停止所有策略
        for strategy in self._strategies.values():
            strategy.stop()

        self._strategies.clear()
        self._signals.clear()

        logger.info("策略智能体已清理")

    async def _execute_cycle(self):
        """执行周期"""
        # 执行所有活跃策略
        for strategy_name in self._active_strategies:
            await self._execute_strategy_cycle(strategy_name)

        await asyncio.sleep(1)

    async def _load_default_strategies(self):
        """加载默认策略"""
        try:
            # 导入策略类
            from strategies.base_strategy import BaseStrategy
            from strategies.dynamics_strategy import DynamicsStrategy
            from strategies.passivbot_integrator import PassivbotIntegrator
            from strategies.combined_strategy import CombinedStrategy
            from strategies.machine_learning_strategy import MachineLearningStrategy
            from strategies.arbitrage_strategy import ArbitrageStrategy
            from strategies.cross_market_arbitrage_strategy import CrossMarketArbitrageStrategy
            
            # 创建动力学策略
            dynamics_config = {
                "dynamics": {
                    "ε": 0.85,
                    "G_eff": 1.2e-3,
                    "n": 3,
                    "η": 0.75,
                    "γ": 0.1,
                    "κ": 2.5,
                    "λ": 3.0,
                    "t_coll": 0.1,
                }
            }

            dynamics_strategy = DynamicsStrategy(config=dynamics_config)
            self._strategies["DynamicsStrategy"] = dynamics_strategy

            logger.info(f"加载策略成功: DynamicsStrategy")

            # 创建Passivbot策略
            passivbot_config = {
                "broker": "okx",
                "symbol": "BTC-USDT-SWAP",
                "timeframe": "1h",
                "strategy": "default",
            }

            passivbot_strategy = PassivbotIntegrator(config=passivbot_config)
            self._strategies["PassivbotStrategy"] = passivbot_strategy

            logger.info(f"加载策略成功: PassivbotStrategy")

            # 创建机器学习策略
            ml_config = {
                "window_size": 20,
                "threshold": 0.001,
                "lookback": 100
            }

            ml_strategy = MachineLearningStrategy(config=ml_config)
            self._strategies["MachineLearningStrategy"] = ml_strategy

            logger.info(f"加载策略成功: MachineLearningStrategy")

            # 创建套利策略
            arb_config = {
                "arb_pairs": [
                    {
                        "inst_id1": "BTC-USDT-SWAP",
                        "inst_id2": "BTC-USDT",
                        "ratio": 1.0
                    },
                    {
                        "inst_id1": "ETH-USDT-SWAP",
                        "inst_id2": "ETH-USDT",
                        "ratio": 1.0
                    }
                ],
                "min_profit": 0.001,
                "max_trade_amount": 0.01
            }

            arb_strategy = ArbitrageStrategy(config=arb_config)
            self._strategies["ArbitrageStrategy"] = arb_strategy

            logger.info(f"加载策略成功: ArbitrageStrategy")

            # 创建组合策略
            combined_config = {
                "sub_strategies": [
                    {
                        "name": "DynamicsStrategy",
                        "class": DynamicsStrategy,
                        "config": dynamics_config,
                        "weight": 0.3,
                    },
                    {
                        "name": "PassivbotStrategy",
                        "class": PassivbotIntegrator,
                        "config": passivbot_config,
                        "weight": 0.3,
                    },
                    {
                        "name": "MachineLearningStrategy",
                        "class": MachineLearningStrategy,
                        "config": ml_config,
                        "weight": 0.2,
                    },
                    {
                        "name": "ArbitrageStrategy",
                        "class": ArbitrageStrategy,
                        "config": arb_config,
                        "weight": 0.2,
                    },
                ]
            }

            combined_strategy = CombinedStrategy(config=combined_config)
            self._strategies["CombinedStrategy"] = combined_strategy

            logger.info(f"加载策略成功: CombinedStrategy")

            # 创建跨市场套利策略
            cross_market_config = {
                "arbitrage_threshold": 0.5,
                "max_trade_amount": 10000,
                "min_trade_amount": 100,
                "exchanges": ["okx", "binance"],
                "trading_pairs": ["BTC/USDT", "ETH/USDT"],
                "polling_interval": 1,
                "max_position": 0.1,
                "fee_estimate": 0.1,
                "profit_threshold": 0.1
            }

            cross_market_strategy = CrossMarketArbitrageStrategy(config=cross_market_config)
            self._strategies["CrossMarketArbitrageStrategy"] = cross_market_strategy

            logger.info(f"加载策略成功: CrossMarketArbitrageStrategy")

        except Exception as e:
            logger.error(f"加载默认策略失败: {e}")

    async def _execute_strategy_cycle(self, strategy_name: str):
        """执行策略周期"""
        strategy = self._strategies.get(strategy_name)
        if not strategy:
            return

        try:
            # 获取市场数据
            market_data = {}
            if self.market_data_agent:
                ticker = self.market_data_agent.get_ticker(self._default_inst_id)
                if ticker:
                    market_data = {
                        "inst_id": self._default_inst_id,
                        "price": float(ticker.get("last", 0)),
                        "timestamp": ticker.get("ts", 0),
                    }

            # 执行策略
            if market_data:
                signal = strategy.execute(market_data)

                if signal:
                    await self._process_signal(signal)

        except Exception as e:
            logger.error(f"策略执行错误: {e}")

    async def _process_signal(self, signal: Dict):
        """处理交易信号"""
        logger.info(f"策略信号: {signal}")

        # 缓存信号
        self._signals.append(signal)
        if len(self._signals) > 100:
            self._signals = self._signals[-100:]

        # 发送信号事件
        await self.event_bus.publish_async(
            Event(
                type=EventType.STRATEGY_SIGNAL,
                source=self.agent_id,
                data={"signal": signal},
            )
        )

        # 发送信号通知
        signal_msg = MessageTemplates.strategy_signal(
            sender=self.agent_id,
            strategy_name=signal.get("strategy", "unknown"),
            signal=signal,
        )
        await self.send_message(signal_msg)

    async def _handle_strategy_command(self, message: Message):
        """处理策略命令"""
        payload = message.payload
        action = payload.get("action")

        if action == "activate":
            result = await self.activate_strategy(payload.get("strategy_name"))
        elif action == "deactivate":
            result = await self.deactivate_strategy(payload.get("strategy_name"))
        elif action == "list":
            result = {
                "success": True,
                "strategies": list(self._strategies.keys()),
                "active_strategies": self._active_strategies,
            }
        else:
            result = {"success": False, "error": "未知命令"}

        response = Message.create_response(
            sender=self.agent_id,
            receiver=message.sender,
            request_message=message,
            payload=result,
        )
        await self.send_message(response)

    async def _on_market_data(self, event: Event):
        """处理市场数据更新"""
        self.metrics.update_activity()

    # ========== 公共接口 ==========

    async def activate_strategy(self, strategy_name: str) -> Dict:
        """
        激活策略

        Args:
            strategy_name: 策略名称

        Returns:
            Dict: 结果
        """
        if strategy_name not in self._strategies:
            return {"success": False, "error": f"策略不存在: {strategy_name}"}

        # 检查策略是否已经激活
        if strategy_name in self._active_strategies:
            return {"success": False, "error": f"策略已经激活: {strategy_name}"}

        # 启动策略
        strategy = self._strategies[strategy_name]
        strategy.start()
        self._active_strategies.append(strategy_name)

        logger.info(f"策略已激活: {strategy_name}")
        return {"success": True, "strategy": strategy_name}

    async def deactivate_strategy(self, strategy_name: str = None) -> Dict:
        """
        停用策略

        Args:
            strategy_name: 策略名称，None表示停用所有策略

        Returns:
            Dict: 结果
        """
        if not self._active_strategies:
            return {"success": False, "error": "没有激活的策略"}

        if strategy_name:
            # 停用指定策略
            if strategy_name not in self._active_strategies:
                return {"success": False, "error": f"策略未激活: {strategy_name}"}

            # 停止策略
            strategy = self._strategies.get(strategy_name)
            if strategy:
                strategy.stop()

            self._active_strategies.remove(strategy_name)
            logger.info(f"策略已停用: {strategy_name}")
        else:
            # 停用所有策略
            for name in self._active_strategies:
                strategy = self._strategies.get(name)
                if strategy:
                    strategy.stop()

            self._active_strategies.clear()
            logger.info("所有策略已停用")

        return {"success": True}

    def get_active_strategies(self) -> List[str]:
        """获取当前激活的策略列表"""
        return self._active_strategies

    def get_signals(self, limit: int = 10) -> List[Dict]:
        """获取最近信号"""
        return self._signals[-limit:]

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        base_status = super().get_status()
        base_status.update(
            {
                "strategies": list(self._strategies.keys()),
                "active_strategies": self._active_strategies,
                "signal_count": len(self._signals),
            }
        )
        return base_status
